window.onerror = function(msg, url, lineNo, columnNo, error) {
    const container = document.getElementById('debug-log-container');
    if (container) {
        const div = document.createElement('div');
        div.className = 'mb-1 text-neonRed font-bold';
        div.innerText = `[JS ERROR] ${msg} at line ${lineNo}`;
        container.appendChild(div);
    }
    return false;
};

let currentMarket = localStorage.getItem('selectedMarket') || 'spot';
let ws = null;
let authToken = localStorage.getItem('bot_token') || sessionStorage.getItem('bot_token');
let reconnectTimeout = 1000;
let dataStore = {
    spot: { trades: [], logs: [], stats: null, status: null, globalConfig: null },
    futures: { trades: [], logs: [], stats: null, status: null, globalConfig: null }
};
let isSpotPaused = false;
let isFuturesPaused = false;

async function fetchBotControl() {
    try {
        const token = localStorage.getItem('bot_token') || sessionStorage.getItem('bot_token');
        const response = await fetch('/api/bot_control', {
            headers: {'Authorization': token ? `Bearer ${token}` : ''}
        });
        const data = await response.json();
        updatePauseUI(data);
    } catch (e) {
        console.error("Error fetching bot control:", e);
    }
}

function updatePauseUI(data) {
    isSpotPaused = data.spot_paused;
    isFuturesPaused = data.futures_paused;
    
    const btn = document.getElementById('toggle-pause-btn');
    const textSpan = document.getElementById('pause-text');
    
    const isPaused = currentMarket === 'spot' ? isSpotPaused : isFuturesPaused;
    
    if (isPaused) {
        btn.className = "px-4 py-1.5 rounded-full bg-neonRed/20 text-neonRed text-sm font-bold border border-neonRed/50 uppercase tracking-widest hover:bg-neonRed/30 transition-colors animate-pulse";
        textSpan.innerText = "RESUME " + currentMarket.toUpperCase();
    } else {
        btn.className = "px-4 py-1.5 rounded-full bg-slate-800 text-slate-300 text-sm font-bold border border-slate-600 uppercase tracking-widest hover:bg-slate-700 transition-colors";
        textSpan.innerText = "PAUSE " + currentMarket.toUpperCase();
    }
}

async function togglePause() {
    const token = localStorage.getItem('bot_token') || sessionStorage.getItem('bot_token');
    const targetMarket = currentMarket;
    const newStatus = targetMarket === 'spot' ? !isSpotPaused : !isFuturesPaused;
    try {
        await fetch('/api/toggle_pause', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': token ? `Bearer ${token}` : ''
            },
            body: JSON.stringify({market: targetMarket, paused: newStatus})
        });
    } catch (e) {
        console.error(e);
    }
}

function setMarket(market) {
    currentMarket = market;
    localStorage.setItem('selectedMarket', market);
    
    const spotTab = document.getElementById('tab-spot');
    const futuresTab = document.getElementById('tab-futures');
    const labTab = document.getElementById('tab-lab');
    const monitorView = document.getElementById('trading-monitor-view');
    const labView = document.getElementById('ai-lab-view');
    
    const activeClass = "tab-active px-6 py-2 rounded-lg text-sm font-bold uppercase tracking-widest transition-all";
    const inactiveClass = "px-6 py-2 rounded-lg text-slate-400 text-sm font-bold uppercase tracking-widest transition-all hover:text-white border border-transparent";
    
    if (spotTab) spotTab.className = (market === 'spot') ? activeClass : inactiveClass;
    if (futuresTab) futuresTab.className = (market === 'futures') ? activeClass : inactiveClass;
    if (labTab) labTab.className = (market === 'lab') ? activeClass : inactiveClass;
    
    if (market === 'lab') {
        if (monitorView) monitorView.classList.add('hidden');
        if (labView) labView.classList.remove('hidden');
        fetchLeaderboard();
        return;
    } else {
        if (monitorView) monitorView.classList.remove('hidden');
        if (labView) labView.classList.add('hidden');
    }
    
    document.getElementById('positions-header').innerText = `Live Positions (${market === 'spot' ? 'Spot' : 'Futures'})`;
    document.getElementById('trades-header').innerText = `Execution Log (${market === 'spot' ? 'Spot' : 'Futures'})`;
    document.getElementById('logs-header').innerText = `System Debug Log (${market === 'spot' ? 'Spot' : 'Futures'})`;
    document.getElementById('live-balance-header').innerText = `Live Balance (${market === 'spot' ? 'Spot' : 'Futures'})`;
    
    updatePauseUI({spot_paused: isSpotPaused, futures_paused: isFuturesPaused});
    
    if (market === 'futures') {
        document.getElementById('futures-badge').classList.remove('hidden');
        document.getElementById('positions-thead').innerHTML = `
            <tr class="bg-slate-900/40">
                <th class="p-4 text-xs font-bold uppercase tracking-wider text-slate-400">Asset</th>
                <th class="p-4 text-xs font-bold uppercase tracking-wider text-slate-400 text-right">Size (Side)</th>
                <th class="p-4 text-xs font-bold uppercase tracking-wider text-slate-400 text-right">Entry / Mark</th>
                <th class="p-4 text-xs font-bold uppercase tracking-wider text-slate-400 text-right">Funding / L-S</th>
                <th class="p-4 text-xs font-bold uppercase tracking-wider text-slate-400 text-right">Margin</th>
                <th class="p-4 text-xs font-bold uppercase tracking-wider text-slate-400 text-right">PNL ($)</th>
                <th class="p-4 text-xs font-bold uppercase tracking-wider text-slate-400 text-right">PNL (%)</th>
            </tr>
        `;
    } else {
        document.getElementById('futures-badge').classList.add('hidden');
        document.getElementById('positions-thead').innerHTML = `
            <tr class="bg-slate-900/40">
                <th class="p-4 text-xs font-bold uppercase tracking-wider text-slate-400">Asset</th>
                <th class="p-4 text-xs font-bold uppercase tracking-wider text-slate-400 text-right">Quantity</th>
                <th class="p-4 text-xs font-bold uppercase tracking-wider text-slate-400 text-right">Avg Buy Price</th>
                <th class="p-4 text-xs font-bold uppercase tracking-wider text-slate-400 text-right">Current Price</th>
                <th class="p-4 text-xs font-bold uppercase tracking-wider text-slate-400 text-right">PNL ($)</th>
                <th class="p-4 text-xs font-bold uppercase tracking-wider text-slate-400 text-right">PNL (%)</th>
            </tr>
        `;
    }
    
    if (dataStore[market] && dataStore[market].status) updateStatusUI(dataStore[market].status, dataStore[market].globalConfig);
    if (dataStore[market] && dataStore[market].trades) updateTradesUI(dataStore[market].trades);
    if (dataStore[market] && dataStore[market].logs) renderLogsUI(dataStore[market].logs);
    if (dataStore[market] && dataStore[market].stats) renderStatsUI(dataStore[market].stats);
}

function startApp() {
    document.getElementById('login-modal').classList.add('hidden');
    document.getElementById('app-container').classList.remove('hidden');
    fetchBotControl();
    setMarket(currentMarket);
    connectWebSocket();
}

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
            updatePauseUI(message.data);
        } else if (message.type === "status_update") {
            dataStore['spot'].globalConfig = message.data;
            dataStore['futures'].globalConfig = message.data;
            dataStore['spot'].status = message.data.spot;
            dataStore['futures'].status = message.data.futures;
            if (currentMarket === 'spot') updateStatusUI(message.data.spot, message.data);
            else updateStatusUI(message.data.futures, message.data);
        } else if (message.type === "trades_update") {
            if (message.is_delta) {
                dataStore[market].trades = [...message.data, ...dataStore[market].trades].slice(0, 50);
            } else {
                dataStore[market].trades = message.data;
            }
            if (currentMarket === market) updateTradesUI(dataStore[market].trades, message.is_delta);
        } else if (message.type === "logs_update") {
            if (message.is_delta) {
                dataStore[market].logs = [...message.data, ...dataStore[market].logs].slice(0, 1000);
            } else {
                dataStore[market].logs = message.data;
            }
            if (currentMarket === market) renderLogsUI(dataStore[market].logs, message.is_delta);
        } else if (message.type === "stats_update") {
            dataStore[market].stats = message.data;
            if (currentMarket === market) renderStatsUI(dataStore[market].stats);
        }
    };

    ws.onclose = (event) => {
        if (event.code === 1008) {
            console.error("Invalid token. Forcing logout.");
            logout();
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

if (authToken) {
    startApp();
}

document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const u = document.getElementById('username').value;
    const p = document.getElementById('password').value;
    const r = document.getElementById('remember').checked;
    
    try {
        const res = await fetch('/api/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username: u, password: p, remember_me: r})
        });
        
        if (res.ok) {
            const data = await res.json();
            authToken = data.token;
            if (r) localStorage.setItem('bot_token', authToken);
            else sessionStorage.setItem('bot_token', authToken);
            
            document.getElementById('login-error').classList.add('hidden');
            startApp();
        } else {
            document.getElementById('login-error').classList.remove('hidden');
            document.getElementById('login-error').innerText = "Invalid credentials. Access Denied.";
        }
    } catch (err) {
        document.getElementById('login-error').classList.remove('hidden');
        document.getElementById('login-error').innerText = "Network Error. Is the backend running?";
    }
});

function logout() {
    localStorage.removeItem('bot_token');
    sessionStorage.removeItem('bot_token');
    if (ws) ws.close();
    window.location.reload();
}

function updateStatusUI(aiStatus, globalConfig) {
    if (!aiStatus || !globalConfig) return;
    document.getElementById('symbol-display').innerText = globalConfig.symbols ? globalConfig.symbols.map(s => s.replace('USDT', '')).join(' • ') : 'None';
    if (globalConfig.fear_greed_index !== undefined && globalConfig.fear_greed_index !== null) {
        document.getElementById('fear-greed-display').innerText = globalConfig.fear_greed_index;
    }
    
    const isPaper = globalConfig.paper_trading === "True";
    const modeBadge = document.getElementById('mode-badge');
    if (isPaper) {
        modeBadge.innerText = "Simulated Paper Trading";
        modeBadge.className = "px-4 py-1.5 rounded-full bg-slate-500/20 text-slate-300 text-sm font-bold border border-slate-500/30 uppercase tracking-widest";
        document.getElementById('live-usdt').innerText = "SIMULATED";
        document.getElementById('live-usdt').classList.add('text-lg', 'text-slate-400');
    } else {
        modeBadge.innerText = "LIVE EXCHANGE SYNC";
        modeBadge.className = "px-4 py-1.5 rounded-full bg-neonRed/10 text-neonRed text-sm font-bold border border-neonRed/30 uppercase tracking-widest animate-pulse";
        document.getElementById('live-usdt').innerText = (aiStatus.live_usdt || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
        document.getElementById('live-usdt').classList.remove('text-lg', 'text-slate-400');
    }
    
    if (aiStatus.is_thinking) {
        document.getElementById('ui-ai-spinner').classList.remove('hidden');
        document.getElementById('ui-chief-brain').classList.add('hidden');
        
        document.getElementById('ui-chief-card').classList.add('border-glow');
        document.getElementById('ui-bull-card').classList.add('shadow-[0_0_15px_rgba(57,255,20,0.2)]');
        document.getElementById('ui-bear-card').classList.add('shadow-[0_0_15px_rgba(255,0,60,0.2)]');
        
        document.getElementById('ui-bull-text').innerHTML = '<span class="animate-pulse">Analyzing momentum and breakouts...</span>';
        document.getElementById('ui-bear-text').innerHTML = '<span class="animate-pulse">Checking risks and invalidation levels...</span>';
        document.getElementById('ui-chief-text').innerHTML = '<span class="animate-pulse">' + escapeHTML(aiStatus.status_message || 'Evaluating...') + '</span>';
    } else {
        document.getElementById('ui-ai-spinner').classList.add('hidden');
        document.getElementById('ui-chief-brain').classList.remove('hidden');
        
        document.getElementById('ui-chief-card').classList.remove('border-glow');
        document.getElementById('ui-bull-card').classList.remove('shadow-[0_0_15px_rgba(57,255,20,0.2)]');
        document.getElementById('ui-bear-card').classList.remove('shadow-[0_0_15px_rgba(255,0,60,0.2)]');
        
        if (aiStatus.ai_debate) {
            const debate = aiStatus.ai_debate;
            document.getElementById('ui-bull-text').innerText = debate.bull || 'No data.';
            document.getElementById('ui-bear-text').innerText = debate.bear || 'No data.';
            document.getElementById('ui-chief-text').innerText = debate.chief_reason || aiStatus.status_message;
            
            document.getElementById('ui-chief-decision').innerText = debate.decision || 'HOLD';
            document.getElementById('ui-chief-risk').innerText = debate.risk_score || '--';
            
            if (debate.decision === 'BUY') {
                document.getElementById('ui-chief-decision').className = 'text-xl font-extrabold tracking-widest text-neonGreen text-glow';
            } else if (debate.decision === 'SELL') {
                document.getElementById('ui-chief-decision').className = 'text-xl font-extrabold tracking-widest text-neonRed text-glow-red';
            } else {
                document.getElementById('ui-chief-decision').className = 'text-xl font-extrabold tracking-widest text-slate-500';
            }
        } else {
            document.getElementById('ui-chief-text').innerText = aiStatus.status_message || 'Waiting for bot cycle...';
        }
    }
    
    const positionsBody = document.getElementById('positions-table-body');
    positionsBody.innerHTML = '';
    if (aiStatus.positions && aiStatus.positions.length > 0) {
        aiStatus.positions.forEach(pos => {
            const tr = document.createElement('tr');
            tr.className = 'hover:bg-slate-800/30 transition-colors';
            
            const pnlAmtColor = pos.pnl_amount > 0 ? 'text-neonGreen text-glow-green' : (pos.pnl_amount < 0 ? 'text-neonRed text-glow-red' : 'text-slate-300');
            const pnlPctColor = pos.pnl_percent > 0 ? 'text-neonGreen text-glow-green' : (pos.pnl_percent < 0 ? 'text-neonRed text-glow-red' : 'text-slate-300');
            
            if (currentMarket === 'futures') {
                const sideColor = pos.position_side === 'LONG' ? 'text-neonGreen' : 'text-neonRed';
                const sideLabel = escapeHTML(pos.position_side || 'N/A');
                
                let formattedFundingRate = '--';
                let frColor = 'text-slate-400';
                if (pos.funding_rate !== undefined && pos.funding_rate !== null) {
                    formattedFundingRate = (Number(pos.funding_rate) * 100).toFixed(4) + '%';
                    frColor = Number(pos.funding_rate) < 0 ? 'text-neonRed' : 'text-neonGreen';
                }
                const formattedLongShortRatio = pos.long_short_ratio !== undefined && pos.long_short_ratio !== null ? Number(pos.long_short_ratio).toFixed(2) : '--';
                
                tr.innerHTML = `
                    <td class="p-4 font-medium text-slate-200">${escapeHTML(pos.symbol)}</td>
                    <td class="p-4 text-right font-mono"><span class="${sideColor} font-bold mr-2">${sideLabel}</span><span class="text-slate-300">${Number(pos.quantity).toFixed(4)}</span></td>
                    <td class="p-4 text-right text-slate-300 font-mono text-xs"><div class="mb-1">E: ${Number(pos.buy_price).toFixed(4)}</div><div>M: ${Number(pos.current_price).toFixed(4)}</div></td>
                    <td class="p-4 text-right text-slate-300 font-mono text-xs"><div class="mb-1">FR: <span class="${frColor}">${escapeHTML(formattedFundingRate)}</span></div><div>L/S: ${escapeHTML(formattedLongShortRatio)}</div></td>
                    <td class="p-4 text-right text-slate-300 font-mono">${pos.margin ? Number(pos.margin).toFixed(2) : '--'}</td>
                    <td class="p-4 text-right font-mono font-bold ${pnlAmtColor}">${pos.pnl_amount > 0 ? '+' : ''}${Number(pos.pnl_amount).toFixed(2)}</td>
                    <td class="p-4 text-right font-mono font-bold ${pnlPctColor}">${pos.pnl_percent > 0 ? '+' : ''}${Number(pos.pnl_percent).toFixed(2)}%</td>
                `;
            } else {
                tr.innerHTML = `
                    <td class="p-4 font-medium text-slate-200">${escapeHTML(pos.symbol)}</td>
                    <td class="p-4 text-right text-slate-300 font-mono">${pos.quantity.toFixed(4)}</td>
                    <td class="p-4 text-right text-slate-300 font-mono">${pos.buy_price.toLocaleString(undefined, {minimumFractionDigits: 4, maximumFractionDigits: 6})}</td>
                    <td class="p-4 text-right text-slate-300 font-mono">${pos.current_price.toLocaleString(undefined, {minimumFractionDigits: 4, maximumFractionDigits: 6})}</td>
                    <td class="p-4 text-right font-mono font-bold ${pnlAmtColor}">${pos.pnl_amount > 0 ? '+' : ''}${pos.pnl_amount.toFixed(2)}</td>
                    <td class="p-4 text-right font-mono font-bold ${pnlPctColor}">${pos.pnl_percent > 0 ? '+' : ''}${pos.pnl_percent.toFixed(2)}%</td>
                `;
            }
            
            positionsBody.appendChild(tr);
        });
    } else {
        const cols = currentMarket === 'futures' ? 7 : 6;
        positionsBody.innerHTML = `<tr><td colspan="${cols}" class="p-8 text-center text-slate-500 italic">No active positions.</td></tr>`;
    }
}

function escapeHTML(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function updateTradesUI(trades, isDelta = false) {
    if (dataStore[currentMarket].stats && dataStore[currentMarket].stats['ALL']) {
        document.getElementById('total-trades').innerText = dataStore[currentMarket].stats['ALL'].wins + dataStore[currentMarket].stats['ALL'].losses;
    } else {
        document.getElementById('total-trades').innerText = dataStore[currentMarket].trades.length;
    }
    
    if (dataStore[currentMarket].trades.length > 0 && dataStore[currentMarket].trades[0].ai_risk_score !== null) {
        const risk = dataStore[currentMarket].trades[0].ai_risk_score;
        document.getElementById('last-risk').innerText = `Last Risk: ${risk}/100`;
    } else {
        document.getElementById('last-risk').innerText = `Last Risk: --`;
    }

    const tbody = document.getElementById('trade-table-body');
    if (!isDelta) {
        tbody.innerHTML = '';
    }
    
    const fragment = document.createDocumentFragment();
    
    trades.forEach(trade => {
        const tr = document.createElement('tr');
        tr.className = "hover:bg-slate-800/30 transition-colors";
        
        const isBuy = trade.side === 'BUY';
        let sideClass = isBuy ? 'text-neonGreen glow-green' : 'text-neonRed glow-red';
        let actionText = isBuy ? 'BUY' : 'SELL';
        
        if (trade.market_type === 'futures') {
            const isClosing = trade.pnl_amount !== null && trade.pnl_amount !== undefined;
            
            // Use actual position_side from API if available
            if (trade.position_side) {
                if (isClosing) {
                    actionText = 'CLOSE ' + trade.position_side;
                    sideClass = 'text-slate-400';
                } else {
                    actionText = trade.position_side; // LONG or SHORT
                    sideClass = trade.position_side === 'LONG' ? 'text-neonGreen glow-green' : 'text-neonRed glow-red';
                }
            } else {
                // Fallback logic if position_side is missing
                if (isClosing) {
                    actionText = isBuy ? 'CLOSE SHORT' : 'CLOSE LONG';
                    sideClass = 'text-slate-400';
                } else {
                    actionText = isBuy ? 'LONG' : 'SHORT';
                    sideClass = isBuy ? 'text-neonGreen glow-green' : 'text-neonRed glow-red';
                }
            }
        }
        
        const d = new Date(trade.timestamp);
        const dateStr = d.toLocaleDateString() + ' <span class="text-slate-500 ml-1">' + d.toLocaleTimeString() + '</span>';
        
        const safeSymbol = escapeHTML(trade.symbol.replace('USDT',''));
        const safeReasoning = escapeHTML(trade.ai_reasoning || '--');
        const safeSide = escapeHTML(trade.side);
        
        const safeFeeAsset = escapeHTML(trade.fee_asset || '');
        const feeStr = (trade.fee !== null && trade.fee !== undefined) ? `${trade.fee.toFixed(4)} ${safeFeeAsset}` : '--';
        const pnlClass = trade.pnl_amount > 0 ? 'text-neonGreen text-glow-green' : (trade.pnl_amount < 0 ? 'text-neonRed text-glow-red' : 'text-slate-300');
        const pnlStr = (trade.pnl_amount !== null && trade.pnl_percent !== null) ? `<span class="${pnlClass}">$${trade.pnl_amount.toFixed(2)} (${trade.pnl_percent.toFixed(2)}%)</span>` : '--';
        
        tr.innerHTML = `
            <td class="p-4 text-sm text-slate-300 font-medium whitespace-nowrap">${dateStr}</td>
            <td class="p-4 font-extrabold tracking-wider ${sideClass}">${actionText} <span class="text-white text-xs ml-1">${safeSymbol}</span></td>
            <td class="p-4 text-sm font-mono text-slate-200 text-right">$${trade.price.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 6})}</td>
            <td class="p-4 text-sm font-mono text-slate-400 text-right">${trade.quantity.toFixed(5)}</td>
            <td class="p-4 text-sm font-mono text-slate-400 text-right">$${trade.margin !== undefined && trade.margin !== null ? trade.margin.toFixed(2) : '--'}</td>
            <td class="p-4 text-sm font-mono text-slate-400 text-right">${feeStr}</td>
            <td class="p-4 text-sm font-mono text-right">${pnlStr}</td>
            <td class="p-4 text-sm text-slate-400 whitespace-normal break-words max-w-xs" title="${safeReasoning}">${safeReasoning}</td>
        `;
        fragment.appendChild(tr);
    });
    
    if (isDelta) {
        tbody.insertBefore(fragment, tbody.firstChild);
        // Prune old rows if too many
        while (tbody.children.length > 50) {
            tbody.removeChild(tbody.lastChild);
        }
    } else {
        tbody.appendChild(fragment);
    }
}

document.getElementById('toggle-near-miss').addEventListener('change', () => {
    renderLogsUI(dataStore[currentMarket].logs);
});
document.getElementById('toggle-routine-evals').addEventListener('change', () => {
    renderLogsUI(dataStore[currentMarket].logs);
});

function renderLogsUI(logsData, isDelta = false) {
    if(!logsData) return;
    const container = document.getElementById('debug-log-container');
    
    if (!isDelta) {
        container.innerHTML = '';
    }
    
    const showNearMiss = document.getElementById('toggle-near-miss').checked;
    const showRoutineEvals = document.getElementById('toggle-routine-evals').checked;
    
    // For delta, logsData are newest first, we want them appended at the bottom, so reverse them.
    // Same for initial load.
    const sortedLogs = [...logsData].reverse();
    
    const fragment = document.createDocumentFragment();
    
    sortedLogs.forEach(log => {
        if (log.level === 'NEAR_MISS' && !showNearMiss) return;
        if (!showRoutineEvals && log.message.includes('-> Result: HOLD')) return;

        const div = document.createElement('div');
        div.className = 'mb-1';
        
        const d = new Date(log.timestamp);
        const timeStr = d.toLocaleTimeString([], {hour12: false}) + '.' + String(d.getMilliseconds()).padStart(3, '0');
        
        let colorClass = 'text-slate-400';
        if (log.level === 'ERROR') colorClass = 'text-neonRed font-bold';
        else if (log.level === 'WARNING') colorClass = 'text-orange-400';
        else if (log.level === 'INFO') colorClass = 'text-neonCyan';
        else if (log.level === 'NEAR_MISS') colorClass = 'text-yellow-500 opacity-60';
        
        const safeLevel = escapeHTML(log.level);
        const safeMessage = escapeHTML(log.message);
        
        div.innerHTML = `<span class="text-slate-500 mr-2">[${escapeHTML(timeStr)}]</span> <span class="${colorClass}">[${safeLevel}] ${safeMessage}</span>`;
        fragment.appendChild(div);
    });
    
    container.appendChild(fragment);
    
    // Prune old logs to prevent DOM bloat
    while (container.children.length > 500) {
        container.removeChild(container.firstChild);
    }
    
    container.scrollTop = container.scrollHeight;
}

let selectedTimeframe = "ALL";

document.getElementById('pnl-timeframe').addEventListener('change', (e) => {
    selectedTimeframe = e.target.value;
    renderStatsUI(dataStore[currentMarket].stats);
});

function renderStatsUI(statsData) {
    if(!statsData || !statsData[selectedTimeframe]) return;
    const data = statsData[selectedTimeframe];
    document.getElementById('win-rate').innerText = `${data.win_rate.toFixed(1)}%`;
    document.getElementById('win-loss-count').innerText = `${data.wins}W - ${data.losses}L`;
    
    const pnlEl = document.getElementById('cumulative-pnl');
    pnlEl.innerText = `${data.cumulative_pnl >= 0 ? '+' : ''}$${data.cumulative_pnl.toFixed(2)}`;
    pnlEl.className = data.cumulative_pnl >= 0 ? 'text-sm font-bold text-neonGreen text-glow-green' : 'text-sm font-bold text-neonRed text-glow-red';
    
    const pctEl = document.getElementById('pnl-percent');
    pctEl.innerText = `${data.pnl_percent >= 0 ? '+' : ''}${data.pnl_percent.toFixed(2)}%`;
    pctEl.className = data.pnl_percent >= 0 ? 'text-xs font-bold text-neonGreen text-glow-green' : 'text-xs font-bold text-neonRed text-glow-red';
    
    if (statsData['ALL']) {
        document.getElementById('total-trades').innerText = statsData['ALL'].wins + statsData['ALL'].losses;
    }
}

// ==========================================
// AI STRATEGY LAB & LEADERBOARD UI
// ==========================================

async function fetchLeaderboard() {
    const container = document.getElementById('leaderboard-cards-container');
    if (!container) return;
    
    container.innerHTML = `
        <div class="glass-card p-8 rounded-2xl text-center text-slate-400">
            <p class="animate-pulse text-neonCyan font-bold">🧬 Synthesizing & Fetching Alpha Leaderboard...</p>
        </div>
    `;
    
    try {
        const res = await fetch('/api/lab/leaderboard');
        const data = await res.json();
        const strategies = data.strategies || [];
        
        if (strategies.length === 0) {
            container.innerHTML = `
                <div class="glass-card p-8 rounded-2xl text-center text-slate-400 border border-slate-700">
                    <p class="text-base font-bold text-white mb-2">No Synthesized Strategies Found Yet</p>
                    <p class="text-xs">Run <code class="text-neonCyan">python bot_strategy_synthesizer.py</code> locally on your PC to evolve blueprints across 20 symbols!</p>
                </div>
            `;
            return;
        }
        
        container.innerHTML = "";
        window.currentLeaderboardStrategies = strategies;
        strategies.forEach((strat, idx) => {
            const rankBadge = idx === 0 ? "🏆 #1 ALPHA GENOME" : `#${strat.rank} BLUEPRINT`;
            const badgeColor = idx === 0 ? "bg-amber-500/20 text-amber-300 border-amber-500/50 shadow-[0_0_15px_rgba(245,158,11,0.3)]" : "bg-slate-800 text-slate-300 border-slate-700";
            
            const params = strat.parameters || {};
            const paramStr = JSON.stringify(params, null, 2);
            
            const card = document.createElement('div');
            card.className = `glass-card p-6 rounded-2xl border transition-all duration-300 hover:scale-[1.01] ${idx === 0 ? 'border-amber-500/40 bg-gradient-to-br from-amber-500/5 to-transparent' : 'border-slate-800 hover:border-slate-700'}`;
            
            card.innerHTML = `
                <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-slate-800/80 pb-4 mb-4">
                    <div>
                        <div class="flex items-center gap-3">
                            <span class="px-3 py-1 rounded-full text-xs font-extrabold border tracking-wider uppercase ${badgeColor}">
                                ${rankBadge}
                            </span>
                            <h3 class="text-lg font-extrabold text-white tracking-wide">${escapeHTML(strat.name || 'Blueprint')}</h3>
                        </div>
                    </div>
                    <button onclick="copyAICommandFromIndex(${idx})" class="px-4 py-2 rounded-xl bg-gradient-to-r from-neonCyan/20 to-blue-500/20 text-neonCyan font-bold text-xs uppercase tracking-widest border border-neonCyan/40 hover:bg-neonCyan/30 transition-all shadow-[0_0_10px_rgba(0,240,255,0.2)] flex items-center gap-2">
                        <span>📋</span> Copy AI Command
                    </button>
                </div>
                
                <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
                    <div class="bg-slate-900/60 p-3 rounded-xl border border-slate-800">
                        <span class="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">1M Return</span>
                        <span class="text-lg font-extrabold ${strat.net_profit_1m >= 0 ? 'text-neonGreen' : 'text-neonRed'}">${strat.net_profit_1m >= 0 ? '+' : ''}${strat.net_profit_1m}%</span>
                        <span class="text-[11px] block ${strat.net_profit_1m >= 0 ? 'text-neonGreen/80' : 'text-neonRed/80'} font-mono">(${strat.net_profit_1m_dollar !== undefined ? (strat.net_profit_1m_dollar >= 0 ? '+$' : '-$') + Math.abs(strat.net_profit_1m_dollar) : '$' + (strat.net_profit_1m * 10).toFixed(2)})</span>
                    </div>
                    <div class="bg-slate-900/60 p-3 rounded-xl border border-slate-800">
                        <span class="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">3M Return</span>
                        <span class="text-lg font-extrabold ${strat.net_profit_3m >= 0 ? 'text-neonGreen' : 'text-neonRed'}">${strat.net_profit_3m >= 0 ? '+' : ''}${strat.net_profit_3m}%</span>
                        <span class="text-[11px] block ${strat.net_profit_3m >= 0 ? 'text-neonGreen/80' : 'text-neonRed/80'} font-mono">(${strat.net_profit_3m_dollar !== undefined ? (strat.net_profit_3m_dollar >= 0 ? '+$' : '-$') + Math.abs(strat.net_profit_3m_dollar) : '$' + (strat.net_profit_3m * 10).toFixed(2)})</span>
                    </div>
                    <div class="bg-slate-900/60 p-3 rounded-xl border border-slate-800">
                        <span class="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">6M Return</span>
                        <span class="text-lg font-extrabold ${strat.net_profit_6m >= 0 ? 'text-neonGreen' : 'text-neonRed'}">${strat.net_profit_6m >= 0 ? '+' : ''}${strat.net_profit_6m}%</span>
                        <span class="text-[11px] block ${strat.net_profit_6m >= 0 ? 'text-neonGreen/80' : 'text-neonRed/80'} font-mono">(${strat.net_profit_6m_dollar !== undefined ? (strat.net_profit_6m_dollar >= 0 ? '+$' : '-$') + Math.abs(strat.net_profit_6m_dollar) : '$' + (strat.net_profit_6m * 10).toFixed(2)})</span>
                    </div>
                    <div class="bg-slate-900/60 p-3 rounded-xl border ${idx === 0 ? 'border-amber-500/30 bg-amber-500/10' : 'border-slate-800'}">
                        <span class="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">1Y Annualized</span>
                        <span class="text-xl font-extrabold ${strat.net_profit_1y >= 0 ? 'text-neonGreen text-glow-green' : 'text-neonRed'}">${strat.net_profit_1y >= 0 ? '+' : ''}${strat.net_profit_1y}%</span>
                        <span class="text-[11px] block ${strat.net_profit_1y >= 0 ? 'text-neonGreen text-glow-green' : 'text-neonRed'} font-mono font-bold">(${strat.net_profit_1y_dollar !== undefined ? (strat.net_profit_1y_dollar >= 0 ? '+$' : '-$') + Math.abs(strat.net_profit_1y_dollar) : '$' + (strat.net_profit_1y * 10).toFixed(2)})</span>
                    </div>
                </div>
                
                <div class="grid grid-cols-1 sm:grid-cols-4 gap-4 mb-4 text-xs bg-black/30 p-3 rounded-xl border border-slate-800/60">
                    <div><span class="text-slate-400 block text-[10px] uppercase font-bold">Win Rate:</span> <span class="text-white font-extrabold text-sm">${strat.win_rate_1y}%</span></div>
                    <div><span class="text-slate-400 block text-[10px] uppercase font-bold">Max Drawdown:</span> <span class="text-neonRed font-extrabold text-sm">-${strat.max_dd}%</span></div>
                    <div><span class="text-slate-400 block text-[10px] uppercase font-bold">Trade Activity:</span> <span class="text-neonCyan font-extrabold text-sm">${strat.total_trades_1y} ไม้</span> <span class="text-[10px] text-slate-400 block">(~${strat.avg_trades_month || (strat.total_trades_1y/12).toFixed(1)} ไม้/เดือน | ~${strat.avg_trades_day || (strat.total_trades_1y/365).toFixed(1)} ไม้/วัน)</span></div>
                    <div><span class="text-slate-400 block text-[10px] uppercase font-bold">Moonshots (>30%):</span> <span class="text-amber-400 font-extrabold text-sm">${strat.moonshots_1y} 🚀</span></div>
                </div>
                
                <div class="bg-black/40 rounded-xl p-3 border border-slate-800/80 font-mono text-xs text-slate-300">
                    <span class="text-slate-500 text-[10px] uppercase block mb-1 font-bold">🧬 Genome DNA Parameters:</span>
                    <pre class="overflow-x-auto text-[11px] text-neonCyan/90">${escapeHTML(paramStr)}</pre>
                </div>
            `;
            container.appendChild(card);
        });
    } catch (err) {
        container.innerHTML = `
            <div class="glass-card p-8 rounded-2xl text-center text-neonRed border border-neonRed/30">
                <p class="font-bold">Error loading Leaderboard: ${escapeHTML(err.message)}</p>
            </div>
        `;
    }
}

function copyAICommandFromIndex(idx) {
    if (!window.currentLeaderboardStrategies || !window.currentLeaderboardStrategies[idx]) return;
    const strat = window.currentLeaderboardStrategies[idx];
    const paramStr = JSON.stringify(strat.parameters || {}, null, 2);
    copyAICommand(strat.rank, strat.name || `Blueprint #${strat.rank}`, paramStr);
}

function copyAICommand(rank, name, paramStr) {
    const cmd = `Antigravity อัปเกรดระบบเทรดใน bot/strategy.py ให้ใช้กลยุทธ์ Blueprint #${rank} (${name}) ตามที่ห้องแล็บค้นพบเลย!\nพารามิเตอร์ DNA:\n${paramStr}`;
    navigator.clipboard.writeText(cmd).then(() => {
        alert("✅ Copied AI Upgrade Command to clipboard!\n\nPaste it into chat to have AI deploy Blueprint #" + rank + "!");
    }).catch(err => {
        prompt("Copy this AI Command:", cmd);
    });
}
