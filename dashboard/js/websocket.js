// websocket.js — Real-time WebSocket lifecycle management and message routing

function setConnectionStatus(status, message) {
    const statusEl = document.getElementById('connection-status');
    if (!statusEl) return;

    statusEl.innerText = message;
    statusEl.className = status === 'online'
        ? 'status-pill status-pill--online'
        : (status === 'error' ? 'status-pill status-pill--error' : 'status-pill status-pill--neutral');
}

function connectWebSocket() {
    if (!shouldReconnect || !authToken) return;
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/ws`;
    ws = new WebSocket(wsUrl);
    setConnectionStatus('neutral', 'CONNECTING');

    ws.onopen = () => {
        reconnectTimeout = 1000;
        const token = localStorage.getItem('bot_token') || sessionStorage.getItem('bot_token');
        ws.send(JSON.stringify({ type: 'auth', token }));
        setConnectionStatus('online', 'STREAMING');
    };

    ws.onmessage = (event) => {
        let message;
        try {
            message = JSON.parse(event.data);
        } catch (error) {
            console.error('Invalid WebSocket message:', error);
            return;
        }

        const market = message.market_type;
        if (message.type === 'bot_control_update') {
            if (typeof updatePauseUI === 'function') updatePauseUI(message.data || {});
            return;
        }

        if (message.type === 'status_update') {
            const statusData = message.data || {};
            dataStore.spot.globalConfig = statusData;
            dataStore.futures.globalConfig = statusData;
            dataStore.spot.status = statusData.spot || null;
            dataStore.futures.status = statusData.futures || null;

            const currentStatus = getTradingMarket() === 'futures' ? statusData.futures : statusData.spot;
            if (currentStatus && typeof updateStatusUI === 'function') {
                updateStatusUI(currentStatus, statusData);
            }
            return;
        }

        const marketData = dataStore[market];
        if (!marketData) return;

        if (message.type === 'stats_update') {
            marketData.stats = message.data || null;
            if (currentMarket === market && typeof renderStatsUI === 'function') {
                renderStatsUI(marketData.stats);
            }
            return;
        }

        if (!Array.isArray(message.data)) return;

        if (message.type === 'trades_update') {
            marketData.trades = message.is_delta
                ? [...message.data, ...marketData.trades].slice(0, 50)
                : [...message.data];
            if (currentMarket === market && typeof updateTradesUI === 'function') {
                updateTradesUI(marketData.trades, message.is_delta);
            }
        } else if (message.type === 'logs_update') {
            marketData.logs = message.is_delta
                ? [...message.data, ...marketData.logs].slice(0, 1000)
                : [...message.data];
            if (currentMarket === market && typeof renderLogsUI === 'function') {
                renderLogsUI(marketData.logs, message.is_delta);
            }
        }
    };

    ws.onclose = (event) => {
        ws = null;
        if (event.code === 1008) {
            console.error('Invalid token. Forcing logout.');
            if (typeof logout === 'function') logout();
            return;
        }
        if (!shouldReconnect || !authToken) return;
        setConnectionStatus('error', 'RECONNECTING');
        window.setTimeout(connectWebSocket, reconnectTimeout);
        reconnectTimeout = Math.min(reconnectTimeout * 2, 30000);
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setConnectionStatus('error', 'CONNECTION ERROR');
    };
}
