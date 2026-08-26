// bot_control.js — Bot controls, page navigation, and application startup

function getAuthHeader() {
    const token = localStorage.getItem('bot_token') || sessionStorage.getItem('bot_token');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
}

function asBoolean(value) {
    return value === true || value === 'true' || value === 'True' || value === 1;
}

async function fetchBotControl() {
    try {
        const response = await fetch('/api/bot_control', { headers: getAuthHeader() });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        updatePauseUI(data);
    } catch (error) {
        console.error('Error fetching bot control:', error);
    }
}

function updatePauseUI(data = {}) {
    if (Object.prototype.hasOwnProperty.call(data, 'spot_paused')) {
        isSpotPaused = asBoolean(data.spot_paused);
    }
    if (Object.prototype.hasOwnProperty.call(data, 'futures_paused')) {
        isFuturesPaused = asBoolean(data.futures_paused);
    }

    const liveToggle = document.getElementById('toggle-allow-live');
    if (liveToggle && Object.prototype.hasOwnProperty.call(data, 'allow_live')) {
        liveToggle.checked = asBoolean(data.allow_live);
    }

    const market = getTradingMarket();
    const btn = document.getElementById('toggle-pause-btn');
    const textSpan = document.getElementById('pause-text');
    if (!market || !btn || !textSpan) return;

    const isPaused = market === 'spot' ? isSpotPaused : isFuturesPaused;
    if (isPaused) {
        btn.className = 'px-4 py-1.5 rounded-full bg-neonRed/20 text-neonRed text-sm font-bold border border-neonRed/50 uppercase tracking-widest hover:bg-neonRed/30 transition-colors animate-pulse';
        textSpan.innerText = `RESUME ${market.toUpperCase()}`;
    } else {
        btn.className = 'px-4 py-1.5 rounded-full bg-slate-800 text-slate-300 text-sm font-bold border border-slate-600 uppercase tracking-widest hover:bg-slate-700 transition-colors';
        textSpan.innerText = `PAUSE ${market.toUpperCase()}`;
    }
}

async function togglePause() {
    const targetMarket = getTradingMarket();
    if (!targetMarket) return;

    const newStatus = targetMarket === 'spot' ? !isSpotPaused : !isFuturesPaused;
    try {
        const response = await fetch('/api/toggle_pause', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
            body: JSON.stringify({ market: targetMarket, paused: newStatus })
        });
        if (!response.ok) await fetchBotControl();
    } catch (error) {
        console.error('Error toggling bot pause state:', error);
        await fetchBotControl();
    }
}

async function toggleExecutionMode(key, value) {
    if (key !== 'allow_live') return;

    try {
        const response = await fetch('/api/toggle_execution_mode', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
            body: JSON.stringify({ [key]: Boolean(value) })
        });
        if (!response.ok) {
            let detail = 'Unable to change live execution guard.';
            try {
                const errorData = await response.json();
                if (typeof errorData.detail === 'string') detail = errorData.detail;
            } catch (error) {
                // Keep the generic message when the server does not return JSON.
            }
            if (typeof showToast === 'function') showToast(detail, 'error');
            else window.alert(detail);
            await fetchBotControl();
        }
    } catch (error) {
        console.error('Error changing execution mode:', error);
        await fetchBotControl();
    }
}

function setMarket(market) {
    const routes = { home: 'index.html', spot: 'spot.html', futures: 'futures.html', lab: 'lab.html' };
    const route = routes[market];
    if (!route) return;

    localStorage.setItem('selectedMarket', market);
    if (!window.location.pathname.endsWith(`/${route}`) && !window.location.pathname.endsWith(route)) {
        window.location.assign(route);
    }
}

function initializeLabPage() {
    if (window.labProgressInterval) clearInterval(window.labProgressInterval);
    if (typeof fetchLeaderboard === 'function') fetchLeaderboard();
    if (typeof fetchLabProgress === 'function') fetchLabProgress();

    window.labProgressInterval = window.setInterval(() => {
        if (typeof fetchLabProgress === 'function') fetchLabProgress();
        if (document.visibilityState === 'visible' && typeof fetchLeaderboard === 'function') fetchLeaderboard();
    }, 5000);
}

function initializeHomePage() {
    localStorage.setItem('selectedMarket', 'home');
    fetchBotControl();
}

function initializeMarketPage() {
    const market = getTradingMarket();
    if (!market) return;

    localStorage.setItem('selectedMarket', market);
    updatePauseUI({ spot_paused: isSpotPaused, futures_paused: isFuturesPaused });
    setViewMode(viewMode);

    const marketData = dataStore[market];
    if (!marketData) return;
    if (marketData.status && typeof updateStatusUI === 'function') {
        updateStatusUI(marketData.status, marketData.globalConfig);
    }
    if (marketData.trades && typeof updateTradesUI === 'function') {
        updateTradesUI(marketData.trades);
    }
    if (marketData.logs && typeof renderLogsUI === 'function') {
        renderLogsUI(marketData.logs);
    }
    if (marketData.stats && typeof renderStatsUI === 'function') {
        renderStatsUI(marketData.stats);
    }
}

function bindDashboardActions() {
    const pauseButton = document.getElementById('toggle-pause-btn');
    if (pauseButton && !pauseButton.dataset.bound) {
        pauseButton.addEventListener('click', togglePause);
        pauseButton.dataset.bound = 'true';
    }

    const liveToggle = document.getElementById('toggle-allow-live');
    if (liveToggle && !liveToggle.dataset.bound) {
        liveToggle.addEventListener('change', (event) => {
            toggleExecutionMode('allow_live', event.target.checked);
        });
        liveToggle.dataset.bound = 'true';
    }

    const paperButton = document.getElementById('view-paper-btn');
    if (paperButton && !paperButton.dataset.bound) {
        paperButton.addEventListener('click', () => setViewMode('PAPER'));
        paperButton.dataset.bound = 'true';
    }

    const liveButton = document.getElementById('view-live-btn');
    if (liveButton && !liveButton.dataset.bound) {
        liveButton.addEventListener('click', () => setViewMode('LIVE'));
        liveButton.dataset.bound = 'true';
    }

    document.querySelectorAll('[data-action="logout"]').forEach((logoutButton) => {
        if (logoutButton.dataset.bound) return;
        logoutButton.addEventListener('click', logout);
        logoutButton.dataset.bound = 'true';
    });
}

function startApp() {
    const loginModal = document.getElementById('login-modal');
    const appCont = document.getElementById('app-container');
    if (loginModal) loginModal.classList.add('hidden');
    if (appCont) appCont.classList.remove('hidden');

    bindDashboardActions();
    if (currentMarket === 'home') {
        initializeHomePage();
    } else if (currentMarket === 'lab') {
        initializeLabPage();
    } else {
        fetchBotControl();
        initializeMarketPage();
    }
    if (typeof connectWebSocket === 'function') connectWebSocket();
}

document.addEventListener('DOMContentLoaded', bindDashboardActions);
