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
let selectedTimeframe = "ALL";
let viewMode = localStorage.getItem('viewMode') || 'PAPER'; // Default to PAPER

function setViewMode(mode) {
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

    // Re-render UIs based on new filter
    if (dataStore[currentMarket].status) {
        if (typeof updateStatusUI === 'function') {
            updateStatusUI(dataStore[currentMarket].status, dataStore[currentMarket].globalConfig);
        }
    }
    if (dataStore[currentMarket].trades) {
        if (typeof updateTradesUI === 'function') {
            updateTradesUI(dataStore[currentMarket].trades);
        }
    }
    if (dataStore[currentMarket].stats) {
        if (typeof renderStatsUI === 'function') {
            renderStatsUI(dataStore[currentMarket].stats);
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
