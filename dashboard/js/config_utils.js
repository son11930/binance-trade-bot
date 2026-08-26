// config_utils.js — Global State, Constants, and Error Logging Utilities

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

// Global State
const supportedMarkets = ['home', 'spot', 'futures', 'lab'];
const pageMarket = document.body && document.body.dataset ? document.body.dataset.market : '';
const storedMarket = localStorage.getItem('selectedMarket');
let currentMarket = supportedMarkets.includes(pageMarket)
    ? pageMarket
    : (supportedMarkets.includes(storedMarket) ? storedMarket : 'spot');
let ws = null;
let authToken = localStorage.getItem('bot_token') || sessionStorage.getItem('bot_token');
let reconnectTimeout = 1000;
let shouldReconnect = true;
let dataStore = {
    home: { trades: [], logs: [], stats: null, status: null, globalConfig: null },
    spot: { trades: [], logs: [], stats: null, status: null, globalConfig: null },
    futures: { trades: [], logs: [], stats: null, status: null, globalConfig: null },
    lab: { trades: [], logs: [], stats: null, status: null, globalConfig: null }
};
let isSpotPaused = false;
let isFuturesPaused = false;
let selectedTimeframe = "ALL";
const storedViewMode = localStorage.getItem('viewMode');
let viewMode = storedViewMode === 'LIVE' ? 'LIVE' : 'PAPER'; // Default to PAPER

function getTradingMarket() {
    return currentMarket === 'futures' ? 'futures' : (currentMarket === 'spot' ? 'spot' : null);
}

function setViewMode(mode) {
    if (mode !== 'PAPER' && mode !== 'LIVE') return;

    viewMode = mode;
    localStorage.setItem('viewMode', mode);
    
    // Update active button classes
    const paperBtn = document.getElementById('view-paper-btn');
    const liveBtn = document.getElementById('view-live-btn');
    
    if (mode === 'PAPER') {
        if (paperBtn) paperBtn.className = "px-3 py-1 rounded-full bg-blue-500/20 text-blue-400 transition-colors";
        if (liveBtn) liveBtn.className = "px-3 py-1 rounded-full text-slate-400 hover:text-white transition-colors";
    } else {
        if (paperBtn) paperBtn.className = "px-3 py-1 rounded-full text-slate-400 hover:text-white transition-colors";
        if (liveBtn) liveBtn.className = "px-3 py-1 rounded-full bg-blue-500/20 text-blue-400 transition-colors";
    }

    if (paperBtn) paperBtn.setAttribute('aria-pressed', String(mode === 'PAPER'));
    if (liveBtn) liveBtn.setAttribute('aria-pressed', String(mode === 'LIVE'));

    // Re-render UIs based on new filter
    const marketData = dataStore[currentMarket];
    if (!marketData) return;

    if (marketData.status) {
        if (typeof updateStatusUI === 'function') {
            updateStatusUI(marketData.status, marketData.globalConfig);
        }
    }
    if (marketData.trades) {
        if (typeof updateTradesUI === 'function') {
            updateTradesUI(marketData.trades);
        }
    }
    if (marketData.stats) {
        if (typeof renderStatsUI === 'function') {
            renderStatsUI(marketData.stats);
        }
    }
}

// XSS Prevention Utility
function escapeHTML(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
