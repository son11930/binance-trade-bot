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
