// ui_trades.js — Trade Execution Log Table and Delta Deduplication

function updateTradesUI(trades, isDelta = false) {
    let visibleTrades = Array.isArray(trades) ? [...trades] : [];
    if (typeof viewMode !== 'undefined') {
        const wantsPaper = (viewMode === 'PAPER');
        visibleTrades = visibleTrades.filter(t => t.paper_trade === wantsPaper);
    }

    const marketData = dataStore[currentMarket];
    const modeStats = marketData && marketData.stats && marketData.stats[viewMode || 'PAPER'];
    if (modeStats && modeStats.ALL) {
        const totalTrEl = document.getElementById('total-trades');
        if (totalTrEl) totalTrEl.innerText = Number(modeStats.ALL.wins || 0) + Number(modeStats.ALL.losses || 0);
    } else {
        const totalTrEl = document.getElementById('total-trades');
        if (totalTrEl) totalTrEl.innerText = visibleTrades.length;
    }
    
    const lastRiskEl = document.getElementById('last-risk');
    if (lastRiskEl) {
        if (visibleTrades.length > 0 && visibleTrades[0].ai_risk_score !== null && visibleTrades[0].ai_risk_score !== undefined) {
            const risk = Number(visibleTrades[0].ai_risk_score);
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
    
    visibleTrades.forEach(trade => {
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
        
        const safeSymbol = escapeHTML(String(trade.symbol || '').replace('USDT', ''));
        const safeReasoning = escapeHTML(trade.ai_reasoning || '--');
        const safeAction = escapeHTML(actionText);
        
        const safeFeeAsset = escapeHTML(trade.fee_asset || '');
        const fee = Number(trade.fee);
        const feeStr = Number.isFinite(fee) ? `${fee.toFixed(4)} ${safeFeeAsset}` : '--';
        const pnlAmount = Number(trade.pnl_amount);
        const pnlPercent = Number(trade.pnl_percent);
        const pnlClass = pnlAmount > 0 ? 'text-neonGreen text-glow-green' : (pnlAmount < 0 ? 'text-neonRed text-glow-red' : 'text-slate-300');
        const pnlStr = Number.isFinite(pnlAmount) && Number.isFinite(pnlPercent)
            ? `<span class="${pnlClass}">$${pnlAmount.toFixed(2)} (${pnlPercent.toFixed(2)}%)</span>`
            : '--';
        const price = Number(trade.price);
        const quantity = Number(trade.quantity);
        const margin = Number(trade.margin);
        const priceStr = Number.isFinite(price) ? price.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 6}) : '--';
        const quantityStr = Number.isFinite(quantity) ? quantity.toFixed(5) : '--';
        const marginStr = Number.isFinite(margin) ? margin.toFixed(2) : '--';
        
        tr.innerHTML = `
            <td class="p-4 text-sm text-slate-300 font-medium whitespace-nowrap">${dateStr}</td>
            <td class="p-4 font-extrabold tracking-wider ${sideClass}">${safeAction} <span class="text-white text-xs ml-1">${safeSymbol}</span></td>
            <td class="p-4 text-sm font-mono text-slate-200 text-right">$${priceStr}</td>
            <td class="p-4 text-sm font-mono text-slate-400 text-right">${quantityStr}</td>
            <td class="p-4 text-sm font-mono text-slate-400 text-right">$${marginStr}</td>
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
