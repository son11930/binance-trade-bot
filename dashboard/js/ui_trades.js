// ui_trades.js — Trade Execution Log Table and Delta Deduplication

function updateTradesUI(trades, isDelta = false) {
    if (typeof viewMode !== 'undefined') {
        const wantsPaper = (viewMode === 'PAPER');
        trades = trades.filter(t => t.paper_trade === wantsPaper);
    }
    
    if (dataStore[currentMarket].stats && dataStore[currentMarket].stats[viewMode || 'PAPER'] && dataStore[currentMarket].stats[viewMode || 'PAPER']['ALL']) {
        const totalTrEl = document.getElementById('total-trades');
        if (totalTrEl) totalTrEl.innerText = dataStore[currentMarket].stats[viewMode || 'PAPER']['ALL'].wins + dataStore[currentMarket].stats[viewMode || 'PAPER']['ALL'].losses;
    } else {
        const totalTrEl = document.getElementById('total-trades');
        if (totalTrEl) totalTrEl.innerText = trades.length;
    }
    
    const lastRiskEl = document.getElementById('last-risk');
    if (lastRiskEl) {
        if (trades.length > 0 && trades[0].ai_risk_score !== null) {
            const risk = trades[0].ai_risk_score;
            lastRiskEl.innerText = `Last Risk: ${risk}/100`;
        } else {
            lastRiskEl.innerText = `Last Risk: --`;
        }
    }

    const tbody = document.getElementById('trade-table-body');
    if (!tbody) return;
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
            if (trade.position_side) {
                if (isClosing) {
                    actionText = 'CLOSE ' + trade.position_side;
                    sideClass = 'text-slate-400';
                } else {
                    actionText = trade.position_side; // LONG or SHORT
                    sideClass = trade.position_side === 'LONG' ? 'text-neonGreen glow-green' : 'text-neonRed glow-red';
                }
            } else {
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
        while (tbody.children.length > 50) {
            tbody.removeChild(tbody.lastChild);
        }
    } else {
        tbody.appendChild(fragment);
    }
}
