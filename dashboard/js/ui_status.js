// ui_status.js — Status Banner, AI Council Cards, and Positions Table Rendering

function updateStatusUI(aiStatus, globalConfig) {
    if (!aiStatus || !globalConfig) return;
    const symDisp = document.getElementById('symbol-display');
    const fgDisp = document.getElementById('fear-greed-display');
    
    if (symDisp) symDisp.innerText = globalConfig.symbols ? globalConfig.symbols.map(s => s.replace('USDT', '')).join(' • ') : 'None';
    if (fgDisp && globalConfig.fear_greed_index !== undefined && globalConfig.fear_greed_index !== null) {
        fgDisp.innerText = globalConfig.fear_greed_index;
    }
    
    const isPaper = globalConfig.paper_trading === "True";
    const modeBadge = document.getElementById('mode-badge');
    const liveUsdt = document.getElementById('live-usdt');
    
    if (modeBadge && liveUsdt) {
        if (isPaper) {
            modeBadge.innerText = "Simulated Paper Trading";
            modeBadge.className = "px-4 py-1.5 rounded-full bg-slate-500/20 text-slate-300 text-sm font-bold border border-slate-500/30 uppercase tracking-widest";
            liveUsdt.innerText = "SIMULATED";
            liveUsdt.classList.add('text-lg', 'text-slate-400');
        } else {
            modeBadge.innerText = "LIVE EXCHANGE SYNC";
            modeBadge.className = "px-4 py-1.5 rounded-full bg-neonRed/10 text-neonRed text-sm font-bold border border-neonRed/30 uppercase tracking-widest animate-pulse";
            liveUsdt.innerText = (aiStatus.live_usdt || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
            liveUsdt.classList.remove('text-lg', 'text-slate-400');
        }
    }
    
    const spinner = document.getElementById('ui-ai-spinner');
    const chiefBrain = document.getElementById('ui-chief-brain');
    const chiefCard = document.getElementById('ui-chief-card');
    const bullCard = document.getElementById('ui-bull-card');
    const bearCard = document.getElementById('ui-bear-card');
    const bullText = document.getElementById('ui-bull-text');
    const bearText = document.getElementById('ui-bear-text');
    const chiefText = document.getElementById('ui-chief-text');
    const chiefDec = document.getElementById('ui-chief-decision');
    const chiefRisk = document.getElementById('ui-chief-risk');
    
    if (aiStatus.is_thinking) {
        if (spinner) spinner.classList.remove('hidden');
        if (chiefBrain) chiefBrain.classList.add('hidden');
        if (chiefCard) chiefCard.classList.add('border-glow');
        if (bullCard) bullCard.classList.add('shadow-[0_0_15px_rgba(57,255,20,0.2)]');
        if (bearCard) bearCard.classList.add('shadow-[0_0_15px_rgba(255,0,60,0.2)]');
        if (bullText) bullText.innerHTML = '<span class="animate-pulse">Analyzing momentum and breakouts...</span>';
        if (bearText) bearText.innerHTML = '<span class="animate-pulse">Checking risks and invalidation levels...</span>';
        if (chiefText) chiefText.innerHTML = '<span class="animate-pulse">' + escapeHTML(aiStatus.status_message || 'Evaluating...') + '</span>';
    } else {
        if (spinner) spinner.classList.add('hidden');
        if (chiefBrain) chiefBrain.classList.remove('hidden');
        if (chiefCard) chiefCard.classList.remove('border-glow');
        if (bullCard) bullCard.classList.remove('shadow-[0_0_15px_rgba(57,255,20,0.2)]');
        if (bearCard) bearCard.classList.remove('shadow-[0_0_15px_rgba(255,0,60,0.2)]');
        
        if (aiStatus.ai_debate) {
            const debate = aiStatus.ai_debate;
            if (bullText) bullText.innerText = debate.bull || 'No data.';
            if (bearText) bearText.innerText = debate.bear || 'No data.';
            if (chiefText) chiefText.innerText = debate.chief_reason || aiStatus.status_message;
            if (chiefDec) chiefDec.innerText = debate.decision || 'HOLD';
            if (chiefRisk) chiefRisk.innerText = debate.risk_score || '--';
            
            if (chiefDec) {
                if (debate.decision === 'BUY') {
                    chiefDec.className = 'text-xl font-extrabold tracking-widest text-neonGreen text-glow';
                } else if (debate.decision === 'SELL') {
                    chiefDec.className = 'text-xl font-extrabold tracking-widest text-neonRed text-glow-red';
                } else {
                    chiefDec.className = 'text-xl font-extrabold tracking-widest text-slate-500';
                }
            }
        } else {
            if (chiefText) chiefText.innerText = aiStatus.status_message || 'Waiting for bot cycle...';
        }
    }
    
    const positionsBody = document.getElementById('positions-table-body');
    if (!positionsBody) return;
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
