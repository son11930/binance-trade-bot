// ui_logs.js — System Debug Console Logs and Performance Statistics Rendering

document.addEventListener('DOMContentLoaded', () => {
    const nearMissEl = document.getElementById('toggle-near-miss');
    const routineEl = document.getElementById('toggle-routine-evals');
    const pnlTfEl = document.getElementById('pnl-timeframe');
    
    if (nearMissEl) {
        nearMissEl.addEventListener('change', () => {
            if (dataStore[currentMarket]) renderLogsUI(dataStore[currentMarket].logs);
        });
    }
    if (routineEl) {
        routineEl.addEventListener('change', () => {
            if (dataStore[currentMarket]) renderLogsUI(dataStore[currentMarket].logs);
        });
    }
    if (pnlTfEl) {
        pnlTfEl.addEventListener('change', (e) => {
            selectedTimeframe = e.target.value;
            if (dataStore[currentMarket]) renderStatsUI(dataStore[currentMarket].stats);
        });
    }
});

function renderLogsUI(logsData, isDelta = false) {
    if (!logsData) return;
    const container = document.getElementById('debug-log-container');
    if (!container) return;
    
    if (!isDelta) {
        container.innerHTML = '';
    }
    
    const nearMissEl = document.getElementById('toggle-near-miss');
    const routineEl = document.getElementById('toggle-routine-evals');
    const showNearMiss = nearMissEl ? nearMissEl.checked : true;
    const showRoutineEvals = routineEl ? routineEl.checked : true;
    
    const sortedLogs = [...logsData].reverse();
    const fragment = document.createDocumentFragment();
    
    sortedLogs.forEach(log => {
        if (log.level === 'NEAR_MISS' && !showNearMiss) return;
        if (!showRoutineEvals && String(log.message || '').includes('-> Result: HOLD')) return;

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
    
    while (container.children.length > 500) {
        container.removeChild(container.firstChild);
    }
    
    container.scrollTop = container.scrollHeight;
}

function renderStatsUI(statsData) {
    if (!statsData) return;
    const currentMode = typeof viewMode !== 'undefined' ? viewMode : 'PAPER';
    const modeData = statsData[currentMode];
    if (!modeData || !modeData[selectedTimeframe]) return;
    const data = modeData[selectedTimeframe];
    
    const winRateEl = document.getElementById('win-rate');
    const winLossEl = document.getElementById('win-loss-count');
    const pnlEl = document.getElementById('cumulative-pnl');
    const pctEl = document.getElementById('pnl-percent');
    
    const winRate = Number(data.win_rate);
    const cumulativePnl = Number(data.cumulative_pnl);
    const pnlPercent = Number(data.pnl_percent);
    const wins = Number(data.wins || 0);
    const losses = Number(data.losses || 0);

    if (winRateEl) winRateEl.innerText = `${Number.isFinite(winRate) ? winRate.toFixed(1) : '0.0'}%`;
    if (winLossEl) winLossEl.innerText = `${wins}W - ${losses}L`;
    
    if (pnlEl) {
        const displayPnl = Number.isFinite(cumulativePnl) ? cumulativePnl : 0;
        pnlEl.innerText = `${displayPnl >= 0 ? '+' : ''}$${displayPnl.toFixed(2)}`;
        pnlEl.className = displayPnl >= 0 ? 'text-sm font-bold text-neonGreen text-glow-green' : 'text-sm font-bold text-neonRed text-glow-red';
    }
    if (pctEl) {
        const displayPercent = Number.isFinite(pnlPercent) ? pnlPercent : 0;
        pctEl.innerText = `${displayPercent >= 0 ? '+' : ''}${displayPercent.toFixed(2)}%`;
        pctEl.className = displayPercent >= 0 ? 'text-xs font-bold text-neonGreen text-glow-green' : 'text-xs font-bold text-neonRed text-glow-red';
    }
    
    if (modeData['ALL']) {
        const totalTrEl = document.getElementById('total-trades');
        if (totalTrEl) totalTrEl.innerText = Number(modeData['ALL'].wins || 0) + Number(modeData['ALL'].losses || 0);
    }
}
