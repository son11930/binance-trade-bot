// websocket.js — Real-Time WebSocket Lifecycle Management and Message Routing

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/ws`;
    
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        const token = localStorage.getItem('bot_token') || sessionStorage.getItem('bot_token');
        ws.send(JSON.stringify({ type: "auth", token: token }));
    };

    ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        const market = message.market_type || 'spot';
        if (message.type === 'bot_control_update') {
            if (typeof updatePauseUI === 'function') updatePauseUI(message.data);
        } else if (message.type === "status_update") {
            dataStore['spot'].globalConfig = message.data;
            dataStore['futures'].globalConfig = message.data;
            dataStore['spot'].status = message.data.spot;
            dataStore['futures'].status = message.data.futures;
            if (typeof updateStatusUI === 'function') {
                if (currentMarket === 'spot') updateStatusUI(message.data.spot, message.data);
                else if (currentMarket === 'futures') updateStatusUI(message.data.futures, message.data);
            }
        } else if (message.type === "trades_update") {
            if (message.is_delta) {
                dataStore[market].trades = [...message.data, ...dataStore[market].trades].slice(0, 50);
            } else {
                dataStore[market].trades = message.data;
            }
            if (currentMarket === market && typeof updateTradesUI === 'function') {
                updateTradesUI(dataStore[market].trades, message.is_delta);
            }
        } else if (message.type === "logs_update") {
            if (message.is_delta) {
                dataStore[market].logs = [...message.data, ...dataStore[market].logs].slice(0, 1000);
            } else {
                dataStore[market].logs = message.data;
            }
            if (currentMarket === market && typeof renderLogsUI === 'function') {
                renderLogsUI(dataStore[market].logs, message.is_delta);
            }
        } else if (message.type === "stats_update") {
            dataStore[market].stats = message.data;
            if (currentMarket === market && typeof renderStatsUI === 'function') {
                renderStatsUI(dataStore[market].stats);
            }
        }
    };

    ws.onclose = (event) => {
        if (event.code === 1008) {
            console.error("Invalid token. Forcing logout.");
            if (typeof logout === 'function') logout();
            return;
        }
        console.log("WebSocket disconnected. Reconnecting in " + reconnectTimeout + "ms");
        setTimeout(connectWebSocket, reconnectTimeout);
        reconnectTimeout = Math.min(reconnectTimeout * 2, 30000);
    };

    ws.onerror = (error) => {
        console.error("WebSocket error:", error);
    };
}
