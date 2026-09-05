// bot_control.js — Bot controls, page navigation, and application startup

function getAuthHeader() {
    const token = localStorage.getItem('bot_token') || sessionStorage.getItem('bot_token');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
}

function asBoolean(value) {
    return value === true || value === 'true' || value === 'True' || value === 1;
}

function getExecutionLane(data, market, mode) {
    const nested = data.execution_controls
        && data.execution_controls[market]
        && data.execution_controls[market][mode];
    if (nested && typeof nested === 'object') return nested;

    const modeKey = `${market}_${mode.toLowerCase()}_paused`;
    if (Object.prototype.hasOwnProperty.call(data, modeKey)) {
        return { paused: asBoolean(data[modeKey]), effective_paused: asBoolean(data[modeKey]) };
    }

    // A response without lane-specific state is from an older server/client.
    // Treat it as paused until the explicit mode state is available.
    return {
        paused: true,
        effective_paused: true,
        legacy_state_missing: true,
    };
}

function updateExecutionLaneUI(mode, lane, data) {
    const button = document.getElementById(`toggle-${mode.toLowerCase()}-pause-btn`);
    const textSpan = document.getElementById(`${mode.toLowerCase()}-pause-text`);
    const status = document.getElementById(`${mode.toLowerCase()}-execution-status`);
    if (!button || !textSpan) return;

    const isLive = mode === 'LIVE';
    const liveUnlocked = asBoolean(data.allow_live) && String(data.active_stage || '').toUpperCase() === 'LIVE';
    const locked = isLive && !liveUnlocked;
    const paused = lane && (Object.prototype.hasOwnProperty.call(lane, 'effective_paused')
        ? asBoolean(lane.effective_paused)
        : asBoolean(lane.paused));
    const marketKillSwitch = lane && asBoolean(lane.market_kill_switch);
    const clearSafetyButton = !isLive
        ? document.getElementById('clear-paper-safety-btn')
        : null;

    if (clearSafetyButton) {
        clearSafetyButton.classList.toggle('hidden', !marketKillSwitch);
        clearSafetyButton.disabled = !marketKillSwitch;
        clearSafetyButton.title = marketKillSwitch
            ? 'Explicitly clear the market-wide safety pause after reviewing the server reason.'
            : '';
    }

    const disabled = locked || (!isLive && marketKillSwitch);
    button.disabled = disabled;
    button.setAttribute('aria-disabled', String(disabled));
    if (locked) {
        button.className = 'execution-lane-button execution-lane-button--live';
        textSpan.innerText = 'LOCKED';
        if (status) status.innerText = 'LOCKED';
        return;
    }

    if (paused) {
        button.className = isLive
            ? 'execution-lane-button execution-lane-button--live animate-pulse'
            : 'execution-lane-button animate-pulse';
        textSpan.innerText = marketKillSwitch ? 'CLEAR SAFETY FIRST' : `RESUME ${mode}`;
        if (status) status.innerText = marketKillSwitch ? 'PAUSED · MARKET SAFETY' : 'PAUSED';
        button.title = marketKillSwitch
            ? 'A market-wide safety pause is active; review the server safety reason before resuming this lane.'
            : `Resume ${mode} execution`;
    } else {
        button.className = isLive
            ? 'execution-lane-button execution-lane-button--live'
            : 'execution-lane-button';
        textSpan.innerText = `PAUSE ${mode}`;
        if (status) status.innerText = 'RUNNING';
        button.title = `Pause ${mode} execution`;
    }
}

async function clearPaperSafetyPause() {
    const targetMarket = getTradingMarket();
    const lane = getExecutionLane(window.lastBotControl || {}, targetMarket, 'PAPER');
    if (!targetMarket || !asBoolean(lane && lane.market_kill_switch)) return;

    const reason = String(window.lastBotControl && window.lastBotControl.pause_reason || '').trim();
    const suffix = reason ? `\n\nServer reason: ${reason.slice(0, 240)}` : '';
    const confirmed = window.confirm(
        `Clear the ${targetMarket.toUpperCase()} market-wide safety pause for PAPER only?` +
        '\nLive trading will remain paused and locked.' + suffix,
    );
    if (!confirmed) return;

    try {
        const response = await fetch('/api/clear_paper_safety_pause', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
            body: JSON.stringify({
                market: targetMarket,
                confirmation: 'CLEAR PAPER SAFETY PAUSE',
            }),
        });
        if (!response.ok) {
            let detail = 'PAPER safety pause could not be cleared.';
            try {
                const errorData = await response.json();
                if (typeof errorData.detail === 'string') detail = errorData.detail;
            } catch (error) {
                // Keep the generic message when the server does not return JSON.
            }
            if (typeof showToast === 'function') showToast(detail, 'error');
            else window.alert(detail);
            return;
        }
        if (typeof showToast === 'function') showToast('PAPER safety pause cleared; PAPER may now evaluate entries.', 'success');
        await fetchBotControl();
    } catch (error) {
        console.error('Error clearing PAPER safety pause:', error);
        await fetchBotControl();
    }
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
    window.lastBotControl = { ...data };
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
    if (!market) return;
    updateExecutionLaneUI('PAPER', getExecutionLane(data, market, 'PAPER'), data);
    updateExecutionLaneUI('LIVE', getExecutionLane(data, market, 'LIVE'), data);
}

async function toggleExecutionPause(mode) {
    const targetMarket = getTradingMarket();
    const normalizedMode = String(mode || '').toUpperCase();
    if (!targetMarket || !['PAPER', 'LIVE'].includes(normalizedMode)) return;

    const lane = getExecutionLane(
        window.lastBotControl || {},
        targetMarket,
        normalizedMode,
    );
    const liveUnlocked = asBoolean(window.lastBotControl && window.lastBotControl.allow_live)
        && String(window.lastBotControl && window.lastBotControl.active_stage || '').toUpperCase() === 'LIVE';
    if (normalizedMode === 'LIVE' && !liveUnlocked) {
        const message = 'LIVE execution is locked by the server. Stage a LIVE strategy and enable the live unlock first.';
        if (typeof showToast === 'function') showToast(message, 'error');
        return;
    }

    const currentPaused = lane && Object.prototype.hasOwnProperty.call(lane, 'effective_paused')
        ? asBoolean(lane.effective_paused)
        : asBoolean(lane && lane.paused);
    try {
        const response = await fetch('/api/toggle_execution_pause', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
            body: JSON.stringify({ market: targetMarket, execution_mode: normalizedMode, paused: !currentPaused })
        });
        if (!response.ok) {
            let detail = `Unable to change ${normalizedMode} execution state.`;
            try {
                const errorData = await response.json();
                if (typeof errorData.detail === 'string') detail = errorData.detail;
            } catch (error) {
                // Keep the generic message when the server does not return JSON.
            }
            if (typeof showToast === 'function') showToast(detail, 'error');
        }
        await fetchBotControl();
    } catch (error) {
        console.error(`Error toggling ${normalizedMode} execution state:`, error);
        await fetchBotControl();
    }
}

// Compatibility shim for a stale page that still calls the old function.
// It is deliberately scoped to PAPER and never calls the ambiguous
// market-wide endpoint, so it cannot release a LIVE lane.
async function togglePause() {
    return toggleExecutionPause('PAPER');
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
    const marketData = dataStore[market];
    if (!marketData) return;
    updatePauseUI(marketData.globalConfig || { spot_paused: isSpotPaused, futures_paused: isFuturesPaused });
    setViewMode(viewMode);

    const selectedStatus = getExecutionStatusForMarket(market, marketData.status);
    if (selectedStatus && typeof updateStatusUI === 'function') {
        updateStatusUI(selectedStatus, marketData.globalConfig);
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
    ['PAPER', 'LIVE'].forEach((mode) => {
        const button = document.getElementById(`toggle-${mode.toLowerCase()}-pause-btn`);
        if (!button || button.dataset.bound) return;
        button.addEventListener('click', () => toggleExecutionPause(mode));
        button.dataset.bound = 'true';
    });

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

    const clearSafetyButton = document.getElementById('clear-paper-safety-btn');
    if (clearSafetyButton && !clearSafetyButton.dataset.bound) {
        clearSafetyButton.addEventListener('click', clearPaperSafetyPause);
        clearSafetyButton.dataset.bound = 'true';
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
