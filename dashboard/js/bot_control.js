// bot_control.js — Bot Pause/Resume Controls, Market Navigation, and Startup

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
    if (!btn || !textSpan) return;
    
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
    
    if (window.labProgressInterval) {
        clearInterval(window.labProgressInterval);
        window.labProgressInterval = null;
    }
    if (market === 'lab') {
        if (monitorView) monitorView.classList.add('hidden');
        if (labView) labView.classList.remove('hidden');
        if (typeof fetchLeaderboard === 'function') fetchLeaderboard();
        if (typeof fetchLabProgress === 'function') fetchLabProgress();
        window.labProgressInterval = setInterval(() => {
            if (typeof fetchLabProgress === 'function') fetchLabProgress();
            if (document.visibilityState === 'visible' && typeof fetchLeaderboard === 'function') fetchLeaderboard();
        }, 5000);
        return;
    } else {
        if (monitorView) monitorView.classList.remove('hidden');
        if (labView) labView.classList.add('hidden');
    }
    
    const posHeader = document.getElementById('positions-header');
    const trdHeader = document.getElementById('trades-header');
    const logHeader = document.getElementById('logs-header');
    const balHeader = document.getElementById('live-balance-header');
    
    if (posHeader) posHeader.innerText = `Live Positions (${market === 'spot' ? 'Spot' : 'Futures'})`;
    if (trdHeader) trdHeader.innerText = `Execution Log (${market === 'spot' ? 'Spot' : 'Futures'})`;
    if (logHeader) logHeader.innerText = `System Debug Log (${market === 'spot' ? 'Spot' : 'Futures'})`;
    if (balHeader) balHeader.innerText = `Live Balance (${market === 'spot' ? 'Spot' : 'Futures'})`;
    
    updatePauseUI({spot_paused: isSpotPaused, futures_paused: isFuturesPaused});
    
    const futBadge = document.getElementById('futures-badge');
    const posThead = document.getElementById('positions-thead');
    
    if (market === 'futures') {
        if (futBadge) futBadge.classList.remove('hidden');
        if (posThead) posThead.innerHTML = `
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
        if (futBadge) futBadge.classList.add('hidden');
        if (posThead) posThead.innerHTML = `
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
    
    if (dataStore[market] && dataStore[market].status && typeof updateStatusUI === 'function') updateStatusUI(dataStore[market].status, dataStore[market].globalConfig);
    if (dataStore[market] && dataStore[market].trades && typeof updateTradesUI === 'function') updateTradesUI(dataStore[market].trades);
    if (dataStore[market] && dataStore[market].logs && typeof renderLogsUI === 'function') renderLogsUI(dataStore[market].logs);
    if (dataStore[market] && dataStore[market].stats && typeof renderStatsUI === 'function') renderStatsUI(dataStore[market].stats);
}

function startApp() {
    const loginModal = document.getElementById('login-modal');
    const appCont = document.getElementById('app-container');
    if (loginModal) loginModal.classList.add('hidden');
    if (appCont) appCont.classList.remove('hidden');
    
    fetchBotControl();
    setMarket(currentMarket);
    if (typeof connectWebSocket === 'function') connectWebSocket();
}
