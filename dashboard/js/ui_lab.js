// ui_lab.js — AI Strategy Lab progress, leaderboard rendering, and promotion actions

function getLabToken() {
    return localStorage.getItem('bot_token') || sessionStorage.getItem('bot_token');
}

function toFiniteNumber(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
}

function formatLabNumber(value, decimals = 2) {
    const number = toFiniteNumber(value);
    return number === null ? '--' : number.toFixed(decimals);
}

function formatLabCount(value) {
    const number = toFiniteNumber(value);
    return number === null ? '--' : Math.max(0, Math.floor(number)).toLocaleString();
}

function formatLabPercent(value) {
    const number = toFiniteNumber(value);
    return number === null ? '--' : `${number >= 0 ? '+' : ''}${number.toFixed(2)}%`;
}

function formatLabCurrency(value) {
    const number = toFiniteNumber(value);
    return number === null ? '--' : `${number >= 0 ? '+$' : '-$'}${Math.abs(number).toFixed(2)}`;
}

function formatLabCostCurrency(value) {
    const number = toFiniteNumber(value);
    return number === null ? '--' : `-$${Math.abs(number).toFixed(2)}`;
}

function formatLabCostPercent(value) {
    const number = toFiniteNumber(value);
    return number === null ? '--' : `-${Math.abs(number).toFixed(2)}%`;
}

function formatLabDrawdown(value) {
    const number = toFiniteNumber(value);
    return number === null ? '--' : `-${Math.abs(number).toFixed(2)}%`;
}

function clampLabPercent(value) {
    const number = toFiniteNumber(value);
    return number === null ? 0 : Math.max(0, Math.min(100, number));
}

function renderLabExplorationSummary(progress) {
    const summary = document.getElementById('lab-exploration-summary');
    if (!summary) return;

    const generated = toFiniteNumber(progress.generated_count ?? progress.screened_count);
    const screened = toFiniteNumber(progress.screened_count ?? progress.generated_count);
    const full = toFiniteNumber(progress.full_evaluated_count);
    const qualified = toFiniteNumber(progress.qualified_count);
    const rejected = toFiniteNumber(progress.rejected_count);
    const retained = toFiniteNumber(progress.retained_leader_count);
    const published = toFiniteNumber(progress.published_leader_count);
    const tpe = toFiniteNumber(progress.tpe_sampled_count);
    const mutants = toFiniteNumber(progress.mutant_count);
    const exploration = toFiniteNumber(progress.exploration_mutant_count);
    const generatedByStrategy = progress.strategy_generated_counts && typeof progress.strategy_generated_counts === 'object'
        ? progress.strategy_generated_counts : {};
    const fullByStrategy = progress.strategy_full_evaluated_counts && typeof progress.strategy_full_evaluated_counts === 'object'
        ? progress.strategy_full_evaluated_counts : {};
    const qualifiedByStrategy = progress.strategy_qualified_counts && typeof progress.strategy_qualified_counts === 'object'
        ? progress.strategy_qualified_counts : {};
    const rejectedByStrategy = progress.strategy_rejected_counts && typeof progress.strategy_rejected_counts === 'object'
        ? progress.strategy_rejected_counts : {};
    const tpeByStrategy = progress.strategy_tpe_counts && typeof progress.strategy_tpe_counts === 'object'
        ? progress.strategy_tpe_counts : {};
    const mutantByStrategy = progress.strategy_mutant_counts && typeof progress.strategy_mutant_counts === 'object'
        ? progress.strategy_mutant_counts : {};
    const explorationByStrategy = progress.strategy_exploration_counts && typeof progress.strategy_exploration_counts === 'object'
        ? progress.strategy_exploration_counts : {};
    const strategies = [...new Set([
        ...Object.keys(generatedByStrategy),
        ...Object.keys(tpeByStrategy),
        ...Object.keys(mutantByStrategy),
        ...Object.keys(explorationByStrategy),
        ...Object.keys(fullByStrategy),
        ...Object.keys(qualifiedByStrategy),
        ...Object.keys(rejectedByStrategy),
    ])].sort();

    if (generated === null && rejected === null && retained === null && published === null && !strategies.length) {
        summary.classList.add('hidden');
        return;
    }

    const metric = (label, value, tone = 'text-white') => `
        <div class="rounded-xl border border-slate-800/80 bg-slate-950/50 p-3">
            <span class="block text-[10px] font-bold uppercase tracking-wider text-slate-500">${label}</span>
            <span class="mt-1 block font-mono text-lg font-black ${tone}">${formatLabCount(value)}</span>
        </div>`;
    const strategyRows = strategies.length
        ? strategies.map((strategy) => `
            <div class="grid grid-cols-[minmax(0,1fr)_repeat(7,auto)] items-center gap-3 border-t border-slate-800/70 py-2 text-xs">
                <span class="truncate font-mono font-bold text-slate-300">${escapeHTML(strategy)}</span>
                <span class="font-mono text-slate-300" title="Generated">${formatLabCount(generatedByStrategy[strategy])}</span>
                <span class="font-mono text-purple-300" title="TPE samples">${formatLabCount(tpeByStrategy[strategy])}</span>
                <span class="font-mono text-blue-300" title="Mutants">${formatLabCount(mutantByStrategy[strategy])}</span>
                <span class="font-mono text-amber-300" title="Exploratory/high-variance mutants">${formatLabCount(explorationByStrategy[strategy])}</span>
                <span class="font-mono text-neonCyan" title="Full evaluated">${formatLabCount(fullByStrategy[strategy])}</span>
                <span class="font-mono text-neonGreen" title="Qualified">${formatLabCount(qualifiedByStrategy[strategy])}</span>
                <span class="font-mono text-rose-300" title="Rejected after full evaluation">${formatLabCount(rejectedByStrategy[strategy])}</span>
            </div>`).join('')
        : '<p class="text-xs text-slate-500">Per-strategy counters will appear after the next batch checkpoint.</p>';

    summary.classList.remove('hidden');
    summary.innerHTML = `
        <section class="glass-card rounded-2xl border border-indigo-400/30 bg-indigo-950/10 p-5 md:p-6" aria-labelledby="lab-exploration-heading">
            <div class="mb-4 flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
                <div>
                    <p class="text-xs font-bold uppercase tracking-[0.22em] text-indigo-300">SEARCH COVERAGE</p>
                    <h2 id="lab-exploration-heading" class="mt-1 text-xl font-extrabold text-white">Exploration and evaluation audit</h2>
                </div>
                <p class="max-w-xl text-xs leading-relaxed text-slate-400">The leaderboard shows retained leaders, not total search. These counters show whether other strategy families were generated, fully evaluated, and qualified.</p>
            </div>
            <div class="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-10">
                ${metric('Generated', generated, 'text-white')}
                ${metric('Screened', screened, 'text-slate-300')}
                ${metric('TPE samples', tpe, 'text-purple-300')}
                ${metric('Mutants', mutants, 'text-blue-300')}
                ${metric('Exploratory mutants', exploration, 'text-amber-300')}
                ${metric('Full evaluated', full, 'text-neonCyan')}
                ${metric('Qualified', qualified, 'text-neonGreen')}
                ${metric('Rejected (full)', rejected, 'text-rose-300')}
                ${metric('Retained archive', retained, 'text-amber-300')}
                ${metric('Published leaders', published, 'text-indigo-300')}
            </div>
            <div class="mt-4 rounded-xl border border-slate-800/80 bg-black/20 px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Strategy family · generated · TPE · mutants · exploratory · full evaluated · qualified · rejected (full)</div>
            <div class="mt-1">${strategyRows}</div>
        </section>
    `;
}

function showToast(message, type = 'info') {
    let region = document.getElementById('toast-region');
    if (!region) {
        region = document.createElement('div');
        region.id = 'toast-region';
        region.className = 'fixed right-4 top-4 z-[60] flex max-w-sm flex-col gap-2';
        region.setAttribute('aria-live', 'polite');
        document.body.appendChild(region);
    }

    const toast = document.createElement('div');
    const colorClass = type === 'success'
        ? 'border-neonGreen/40 text-neonGreen'
        : (type === 'error' ? 'border-neonRed/40 text-neonRed' : 'border-neonCyan/40 text-neonCyan');
    toast.className = `glass-card rounded-xl border bg-slate-950/95 px-4 py-3 text-sm font-semibold shadow-xl ${colorClass}`;
    toast.innerText = String(message || '');
    region.appendChild(toast);
    window.setTimeout(() => toast.remove(), 5000);
}

function renderLabProgress(progress) {
    const banner = document.getElementById('lab-progress-banner');
    if (!banner) return;

    renderLabExplorationSummary(progress);

    const status = String(progress.status || '');
    if (!status || status === 'idle') {
        banner.classList.add('hidden');
        return;
    }

    const isInfinite = progress.total_trials === 0 || progress.total_trials === 'Infinite' || progress.total_trials === null;
    const isRunning = status === 'running' || status === 'starting';
    const current = Math.max(0, Math.floor(toFiniteNumber(progress.current_trial) || 0));
    const total = isInfinite ? 'INFINITE MODE' : formatLabCount(progress.total_trials);
    const totalDb = formatLabCount(progress.total_db_trials === undefined ? current : progress.total_db_trials);
    const bestScore = formatLabNumber(progress.best_score);
    const bestName = escapeHTML(progress.best_strategy_name || 'N/A');
    const elapsed = Math.max(0, Math.floor(toFiniteNumber(progress.elapsed_seconds) || 0));
    const hours = Math.floor(elapsed / 3600);
    const mins = Math.floor((elapsed % 3600) / 60);
    const secs = elapsed % 60;
    const timeStr = hours > 0 ? `${hours}h ${mins}m ${secs}s` : `${mins}m ${secs}s`;
    const pct = isInfinite ? 100 : clampLabPercent(progress.progress_pct);
    const progressLabel = isRunning
        ? (isInfinite ? 'INFINITE RUNNING' : `${formatLabCount(current)} / ${escapeHTML(total)}`)
        : `${formatLabCount(current)} EVALUATED`;
    const statusClass = isRunning
        ? 'border-neonCyan/50 bg-gradient-to-br from-slate-900/95 via-slate-900/90 to-cyan-950/30 shadow-[0_0_30px_rgba(0,240,255,0.15)]'
        : 'border-neonGreen/40 bg-gradient-to-br from-slate-900/95 to-emerald-950/20';
    const iconClass = isRunning
        ? 'bg-neonCyan/20 border border-neonCyan/50 text-neonCyan animate-pulse'
        : 'bg-neonGreen/20 border border-neonGreen/50 text-neonGreen';
    const labelClass = isRunning
        ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
        : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40';
    const progressClass = isRunning
        ? 'bg-gradient-to-r from-cyan-400 via-blue-500 to-purple-500 shadow-[0_0_15px_rgba(0,240,255,0.8)]'
        : 'bg-gradient-to-r from-emerald-400 to-teal-500 shadow-[0_0_15px_rgba(16,185,129,0.8)]';

    banner.classList.remove('hidden');
    banner.innerHTML = `
        <div class="glass-card rounded-3xl border p-6 transition-all duration-500 md:p-8 ${statusClass}">
            <div class="mb-6 flex flex-col items-start justify-between gap-4 border-b border-slate-800/80 pb-5 md:flex-row md:items-center">
                <div class="flex items-center gap-4">
                    <div class="flex h-12 w-12 items-center justify-center rounded-2xl text-2xl shadow-lg ${iconClass}">${isRunning ? 'LAB' : 'OK'}</div>
                    <div>
                        <div class="flex flex-wrap items-center gap-2">
                            <span class="rounded-full px-2.5 py-0.5 text-[10px] font-extrabold uppercase tracking-wider ${labelClass}">${isRunning ? 'AI LAB ACTIVE' : 'COMPLETED'}</span>
                            <span class="font-mono text-xs text-slate-400">Elapsed: ${escapeHTML(timeStr)}</span>
                        </div>
                        <h2 class="mt-1 text-lg font-extrabold uppercase tracking-wide text-white md:text-xl">
                            ${isRunning ? (isInfinite ? 'INFINITE ALPHA EVOLUTION' : 'EVOLVING ALPHA GENOME') : 'ALPHA SYNTHESIS COMPLETED'}
                        </h2>
                    </div>
                </div>
                <div class="flex items-center gap-3 self-end md:self-center">
                    <div class="text-right">
                        <div class="text-xs font-semibold uppercase tracking-wider text-slate-400">Session Progress</div>
                        <div class="font-mono text-lg font-black ${isRunning ? 'text-neonCyan' : 'text-neonGreen'}">${progressLabel}</div>
                    </div>
                    <span class="rounded-2xl border px-4 py-2 font-mono text-sm font-black ${isRunning ? 'border-neonCyan/40 bg-neonCyan/10 text-neonCyan' : 'border-neonGreen/40 bg-neonGreen/10 text-neonGreen'}">${isRunning ? (isInfinite ? '∞' : `${pct.toFixed(1)}%`) : '100%'}</span>
                </div>
            </div>
            <div class="mb-6">
                <div class="mb-2 flex flex-wrap justify-between gap-2 text-xs font-semibold text-slate-400">
                    <span>Current Session: <strong class="text-white">${formatLabCount(current)}</strong> of <strong class="text-white">${escapeHTML(total)}</strong> trials</span>
                    <span>All-Time DB Memory: <strong class="font-mono text-amber-400">${escapeHTML(totalDb)}</strong> total trials</span>
                </div>
                <div class="h-4 w-full overflow-hidden rounded-full border border-slate-700/60 bg-slate-800/90 p-0.5 shadow-inner">
                    <div class="h-full rounded-full transition-all duration-700 ${progressClass}" style="width: ${pct}%"></div>
                </div>
            </div>
            <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div class="flex items-center justify-between rounded-2xl border border-slate-700/60 bg-slate-800/50 p-4 shadow-sm">
                    <div>
                        <div class="text-[11px] font-bold uppercase tracking-wider text-slate-400">Best Blueprint Found So Far</div>
                        <div class="mt-0.5 truncate font-mono text-sm font-extrabold text-neonCyan md:text-base">${bestName}</div>
                    </div>
                </div>
                <div class="flex items-center justify-between rounded-2xl border border-slate-700/60 bg-slate-800/50 p-4 shadow-sm">
                    <div>
                        <div class="text-[11px] font-bold uppercase tracking-wider text-slate-400">Top Fitness Score (Alpha Rating)</div>
                        <div class="mt-0.5 font-mono text-lg font-black text-amber-400 md:text-xl">${escapeHTML(bestScore)} <span class="text-xs font-normal text-slate-400">pts</span></div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

async function fetchLabProgress() {
    const banner = document.getElementById('lab-progress-banner');
    if (!banner) return;

    try {
        const response = await fetch('/api/lab/progress', {
            headers: getLabToken() ? { 'Authorization': `Bearer ${getLabToken()}` } : {}
        });
        if (!response.ok) throw new Error('Lab progress request failed');
        const payload = await response.json();
        const progress = payload && payload.progress && typeof payload.progress === 'object' ? payload.progress : {};
        if (JSON.stringify(window.currentLabProgress) === JSON.stringify(progress)) return;
        window.currentLabProgress = progress;
        renderLabProgress(progress);
    } catch (error) {
        console.error('Failed to fetch lab progress:', error);
    }
}

function renderLeaderboardError(message) {
    const container = document.getElementById('leaderboard-cards-container');
    if (!container) return;
    container.innerHTML = `
        <div class="glass-card rounded-2xl border border-neonRed/30 p-8 text-center text-neonRed">
            <p class="font-bold">${escapeHTML(message)}</p>
        </div>
    `;
}

function appendStrategyAction(button, action, rank, candidateId, artifactHash, name, paramStr) {
    if (!button) return;
    if (button.disabled) return;
    button.addEventListener('click', () => {
        if (action === 'copy') {
            copyAICommand(rank, name, paramStr);
        } else {
            window.deployStrategy(rank, action, candidateId, artifactHash);
        }
    });
}

function buildStrategyCard(strategy, index) {
    const rankNumber = toFiniteNumber(strategy.rank);
    const rank = rankNumber === null ? index + 1 : Math.max(1, Math.floor(rankNumber));
    const name = String(strategy.name || 'Blueprint');
    const candidateId = typeof strategy.candidate_id === 'string' ? strategy.candidate_id : '';
    const artifactHash = typeof strategy.artifact_hash === 'string' ? strategy.artifact_hash : '';
    const qualified = strategy.qualified === true;
    const params = strategy.parameters && typeof strategy.parameters === 'object' ? strategy.parameters : {};
    let paramStr = '{}';
    try {
        paramStr = JSON.stringify(params, null, 2);
    } catch (error) {
        paramStr = '{}';
    }

    const netProfit1m = toFiniteNumber(strategy.net_profit_1m);
    const netProfit3m = toFiniteNumber(strategy.net_profit_3m);
    const netProfit6m = toFiniteNumber(strategy.net_profit_6m);
    const netProfit1y = toFiniteNumber(strategy.net_profit_1y);
    const netProfit1yDollar = toFiniteNumber(strategy.net_profit_1y_dollar);
    const totalTrades = toFiniteNumber(strategy.total_trades_1y) || 0;
    const oosProfit = toFiniteNumber(strategy.oos_profit_1y);
    const oosTrades = toFiniteNumber(strategy.oos_trades_1y) || 0;
    const oosDrawdown = toFiniteNumber(strategy.oos_max_dd);
    const oosProfitFactor = toFiniteNumber(strategy.oos_profit_factor);
    const feePaid1y = toFiniteNumber(strategy.fee_paid_1y_pct);
    const feePaid1yDollar = toFiniteNumber(strategy.fee_paid_1y_dollar);
    const modeledFeeDollar = feePaid1yDollar === null
        ? (feePaid1y === null ? null : feePaid1y * 10)
        : feePaid1yDollar;
    const feeRate = toFiniteNumber(strategy.taker_fee_rate_per_side);
    const roundTripFeeRate = toFiniteNumber(strategy.round_trip_fee_rate);
    const atrSlippageFraction = toFiniteNumber(strategy.atr_slippage_fraction);
    const feeMarketType = typeof strategy.fee_market_type === 'string'
        ? strategy.fee_market_type
        : 'unknown';
    const feeSummary = feeRate === null
        ? 'Cost model metadata unavailable'
        : `${feeMarketType} · Fee ${(feeRate * 100).toFixed(4)}%/side · Round trip ${((roundTripFeeRate === null ? feeRate * 2 : roundTripFeeRate) * 100).toFixed(4)}% · ATR slippage factor ${((atrSlippageFraction === null ? 0 : atrSlippageFraction) * 100).toFixed(2)}% · Funding not included`;
    const averageDollar = toFiniteNumber(strategy.avg_profit_per_trade_dollar);
    const fallbackAverageDollar = netProfit1yDollar === null ? null : netProfit1yDollar / Math.max(1, totalTrades);
    const averageProfitDollar = averageDollar === null ? fallbackAverageDollar : averageDollar;
    const averagePercent = toFiniteNumber(strategy.avg_profit_per_trade_pct);
    const fallbackAveragePercent = netProfit1y === null ? null : netProfit1y / Math.max(1, totalTrades);
    const averageProfitPercent = averagePercent === null ? fallbackAveragePercent : averagePercent;
    const averageClass = averageProfitDollar !== null && averageProfitDollar >= 1
        ? 'text-neonGreen text-glow-green'
        : (averageProfitDollar !== null && averageProfitDollar >= 0.3 ? 'text-amber-400' : 'text-neonRed');
    const actionTitle = qualified ? '' : 'title="Candidate must pass complete evaluation before deployment"';
    const actionDisabled = qualified ? '' : 'disabled';
    const rankBadge = index === 0 ? '#1 ALPHA GENOME' : `#${rank} BLUEPRINT`;
    const badgeColor = index === 0
        ? 'bg-amber-500/20 text-amber-300 border-amber-500/50 shadow-[0_0_15px_rgba(245,158,11,0.3)]'
        : 'bg-slate-800 text-slate-300 border-slate-700';
    const safeMetricClass = (value) => value !== null && value >= 0 ? 'text-neonGreen' : 'text-neonRed';
    const safeSubMetricClass = (value) => value !== null && value >= 0 ? 'text-neonGreen/80' : 'text-neonRed/80';
    const safeParamStr = escapeHTML(paramStr);

    const card = document.createElement('article');
    card.className = `glass-card rounded-2xl border p-6 transition-all duration-300 hover:scale-[1.01] ${index === 0 ? 'border-amber-500/40 bg-gradient-to-br from-amber-500/5 to-transparent' : 'border-slate-800 hover:border-slate-700'}`;
    card.innerHTML = `
        <div class="mb-4 flex flex-col items-start justify-between gap-4 border-b border-slate-800/80 pb-4 md:flex-row md:items-center">
            <div>
                <div class="flex flex-wrap items-center gap-3">
                    <span class="rounded-full border px-3 py-1 text-xs font-extrabold uppercase tracking-wider ${badgeColor}">${escapeHTML(rankBadge)}</span>
                    <h3 class="text-lg font-extrabold tracking-wide text-white">${escapeHTML(name)}</h3>
                </div>
                <span class="mt-2 inline-block rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${qualified ? 'border-neonGreen/30 bg-neonGreen/10 text-neonGreen' : 'border-amber-500/30 bg-amber-500/10 text-amber-300'}">${qualified ? 'QUALIFIED FOR REVIEW' : 'NOT READY FOR DEPLOYMENT'}</span>
            </div>
            <div class="flex flex-wrap gap-2">
                <button type="button" data-lab-action="paper" ${actionDisabled} ${actionTitle} class="rounded-xl border border-blue-500/40 bg-gradient-to-r from-blue-500/20 to-blue-400/10 px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-blue-400 transition-all hover:bg-blue-500/30 disabled:cursor-not-allowed disabled:opacity-40">Stage Paper Review</button>
                <button type="button" data-lab-action="live" ${actionDisabled} ${actionTitle} class="rounded-xl border border-red-500/40 bg-gradient-to-r from-red-500/20 to-orange-500/10 px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-red-400 transition-all hover:bg-red-500/30 disabled:cursor-not-allowed disabled:opacity-40">Request Live Canary</button>
                <button type="button" data-lab-action="copy" class="rounded-xl border border-slate-600 bg-slate-800/60 px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-slate-300 transition-all hover:bg-slate-700">Copy DNA</button>
            </div>
        </div>
        <div class="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div class="rounded-xl border border-slate-800 bg-slate-900/60 p-3"><span class="block text-[10px] font-bold uppercase tracking-wider text-slate-400">1M Return</span><span class="text-lg font-extrabold ${safeMetricClass(netProfit1m)}">${escapeHTML(formatLabPercent(netProfit1m))}</span><span class="block font-mono text-[11px] ${safeSubMetricClass(netProfit1m)}">${escapeHTML(formatLabCurrency(strategy.net_profit_1m_dollar))}</span></div>
            <div class="rounded-xl border border-slate-800 bg-slate-900/60 p-3"><span class="block text-[10px] font-bold uppercase tracking-wider text-slate-400">3M Return</span><span class="text-lg font-extrabold ${safeMetricClass(netProfit3m)}">${escapeHTML(formatLabPercent(netProfit3m))}</span><span class="block font-mono text-[11px] ${safeSubMetricClass(netProfit3m)}">${escapeHTML(formatLabCurrency(strategy.net_profit_3m_dollar))}</span></div>
            <div class="rounded-xl border border-slate-800 bg-slate-900/60 p-3"><span class="block text-[10px] font-bold uppercase tracking-wider text-slate-400">6M Return</span><span class="text-lg font-extrabold ${safeMetricClass(netProfit6m)}">${escapeHTML(formatLabPercent(netProfit6m))}</span><span class="block font-mono text-[11px] ${safeSubMetricClass(netProfit6m)}">${escapeHTML(formatLabCurrency(strategy.net_profit_6m_dollar))}</span></div>
            <div class="rounded-xl border p-3 ${index === 0 ? 'border-amber-500/30 bg-amber-500/10' : 'border-slate-800 bg-slate-900/60'}"><span class="block text-[10px] font-bold uppercase tracking-wider text-slate-400">1Y Backtest Return</span><span class="text-xl font-extrabold ${safeMetricClass(netProfit1y)}">${escapeHTML(formatLabPercent(netProfit1y))}</span><span class="block text-[10px] font-semibold uppercase tracking-wider text-slate-500">Net of modeled costs</span><span class="block font-mono text-[11px] font-bold ${safeSubMetricClass(netProfit1y)}">${escapeHTML(formatLabCurrency(netProfit1yDollar))}</span></div>
        </div>
        <div class="mb-4 grid grid-cols-2 gap-3 rounded-xl border border-slate-800/60 bg-black/30 p-3 text-xs sm:grid-cols-5">
            <div><span class="block text-[10px] font-bold uppercase text-slate-400">Win Rate</span><span class="text-sm font-extrabold text-white">${escapeHTML(formatLabPercent(strategy.win_rate_1y))}</span></div>
            <div><span class="block text-[10px] font-bold uppercase text-slate-400">Max Drawdown</span><span class="text-sm font-extrabold text-neonRed">${escapeHTML(formatLabDrawdown(strategy.max_dd))}</span></div>
            <div><span class="block text-[10px] font-bold uppercase text-slate-400">Trade Activity</span><span class="text-sm font-extrabold text-neonCyan">${escapeHTML(formatLabCount(totalTrades))}</span><span class="block text-[10px] text-slate-400">~${escapeHTML(formatLabNumber(strategy.avg_trades_month === undefined ? totalTrades / 12 : strategy.avg_trades_month, 1))}/mo | ~${escapeHTML(formatLabNumber(strategy.avg_trades_day === undefined ? totalTrades / 365 : strategy.avg_trades_day, 1))}/day</span></div>
            <div><span class="block text-[10px] font-bold uppercase text-slate-400">Avg Profit / Trade</span><span class="text-sm font-extrabold ${averageClass}">${escapeHTML(formatLabCurrency(averageProfitDollar))}</span><span class="block text-[10px] text-slate-400">${escapeHTML(formatLabPercent(averageProfitPercent))}</span></div>
            <div><span class="block text-[10px] font-bold uppercase text-slate-400">Moonshots (&gt;30%)</span><span class="text-sm font-extrabold text-amber-400">${escapeHTML(formatLabCount(strategy.moonshots_1y))}</span></div>
        </div>
        <div class="mb-4 grid grid-cols-2 gap-3 rounded-xl border ${qualified ? 'border-neonGreen/30 bg-neonGreen/5' : 'border-amber-500/30 bg-amber-500/5'} p-3 text-xs sm:grid-cols-5">
            <div><span class="block text-[10px] font-bold uppercase text-slate-400">OOS 1Y Return</span><span class="text-sm font-extrabold ${oosProfit !== null && oosProfit > 0 ? 'text-neonGreen' : 'text-neonRed'}">${escapeHTML(formatLabPercent(oosProfit))}</span></div>
            <div><span class="block text-[10px] font-bold uppercase text-slate-400">OOS Profit Factor</span><span class="text-sm font-extrabold ${oosProfitFactor !== null && oosProfitFactor >= 1.1 ? 'text-neonGreen' : 'text-neonRed'}">${escapeHTML(formatLabNumber(oosProfitFactor, 2))}</span></div>
            <div><span class="block text-[10px] font-bold uppercase text-slate-400">OOS Trades</span><span class="text-sm font-extrabold text-white">${escapeHTML(formatLabCount(oosTrades))}</span><span class="block text-[10px] text-slate-500">minimum 30</span></div>
            <div><span class="block text-[10px] font-bold uppercase text-slate-400">OOS Drawdown</span><span class="text-sm font-extrabold ${oosDrawdown !== null && oosDrawdown <= 15 ? 'text-neonGreen' : 'text-neonRed'}">${escapeHTML(formatLabDrawdown(oosDrawdown))}</span><span class="block text-[10px] text-slate-500">maximum 15%</span></div>
            <div><span class="block text-[10px] font-bold uppercase text-slate-400">Modeled Fee Drag</span><span class="text-sm font-extrabold text-amber-300">${escapeHTML(formatLabCostPercent(feePaid1y))}</span><span class="block text-[10px] text-amber-200/70">${escapeHTML(formatLabCostCurrency(modeledFeeDollar))} IS + OOS</span></div>
        </div>
        <div class="mb-4 rounded-xl border border-slate-800/80 bg-slate-950/50 px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">${escapeHTML(feeSummary)}</div>
        <div class="mb-4 rounded-xl border border-slate-800/80 bg-black/40 p-3 text-xs font-mono text-slate-300">
            <span class="mb-1 block text-[10px] font-bold uppercase text-slate-500">Genome DNA Parameters</span>
            <pre class="overflow-x-auto text-[11px] text-neonCyan/90">${safeParamStr}</pre>
        </div>
        <p class="text-[11px] leading-relaxed text-slate-500">${qualified ? 'Candidate passed the lab qualification gate. Paper review and server-side deployment governance still apply.' : 'Deployment actions stay disabled until the candidate passes the complete evaluation and qualification gates.'}</p>
    `;

    appendStrategyAction(card.querySelector('[data-lab-action="paper"]'), 'PAPER', rank, candidateId, artifactHash, name, paramStr);
    appendStrategyAction(card.querySelector('[data-lab-action="live"]'), 'LIVE', rank, candidateId, artifactHash, name, paramStr);
    appendStrategyAction(card.querySelector('[data-lab-action="copy"]'), 'copy', rank, candidateId, artifactHash, name, paramStr);
    return card;
}

async function fetchLeaderboard() {
    const container = document.getElementById('leaderboard-cards-container');
    if (!container) return;

    if (!window.currentLeaderboardStrategies || window.currentLeaderboardStrategies.length === 0) {
        container.innerHTML = `
            <div class="glass-card rounded-2xl p-8 text-center text-slate-400">
                <p class="animate-pulse font-bold text-neonCyan">Synthesizing and fetching alpha leaderboard...</p>
            </div>
        `;
    }

    try {
        const token = getLabToken();
        const response = await fetch('/api/lab/leaderboard', {
            headers: token ? { 'Authorization': `Bearer ${token}` } : {}
        });
        if (!response.ok) throw new Error('Leaderboard request failed');
        const payload = await response.json();
        const strategies = payload && Array.isArray(payload.strategies) ? payload.strategies : [];

        if (JSON.stringify(window.currentLeaderboardStrategies) === JSON.stringify(strategies)) return;
        window.currentLeaderboardStrategies = strategies;
        renderLabExplorationSummary({
            ...(window.currentLabProgress || {}),
            // The cards are the published snapshot; do not overwrite the
            // backend archive-retention count with the visible card count.
            published_leader_count: toFiniteNumber(window.currentLabProgress && window.currentLabProgress.published_leader_count) ?? strategies.length,
        });

        if (strategies.length === 0) {
            container.innerHTML = `
                <div class="glass-card rounded-2xl border border-slate-700 p-8 text-center text-slate-400">
                    <p class="mb-2 text-base font-bold text-white">No synthesized strategies found yet</p>
                    <p class="text-xs">Run the local strategy lab, then refresh this page after results are uploaded.</p>
                </div>
            `;
            return;
        }

        const fragment = document.createDocumentFragment();
        strategies.forEach((strategy, index) => fragment.appendChild(buildStrategyCard(strategy || {}, index)));
        container.replaceChildren(fragment);
    } catch (error) {
        console.error('Failed to fetch leaderboard:', error);
        renderLeaderboardError('Unable to load the strategy leaderboard. Please refresh and try again.');
    }
}

function copyAICommand(rank, name, paramStr) {
    const command = `Review Blueprint #${rank} (${name}) from the AI Strategy Lab.\nDNA parameters:\n${paramStr}`;
    const copyPromise = navigator.clipboard && navigator.clipboard.writeText
        ? navigator.clipboard.writeText(command)
        : Promise.reject(new Error('Clipboard unavailable'));
    copyPromise
        .then(() => showToast('Strategy DNA copied to the clipboard.', 'success'))
        .catch(() => window.prompt('Copy this strategy DNA:', command));
}

window.deployStrategy = async function(rank, stage, candidateId, artifactHash) {
    if (stage !== 'PAPER' && stage !== 'LIVE') {
        showToast('Unsupported deployment stage.', 'error');
        return;
    }
    if (typeof candidateId !== 'string' || !candidateId || typeof artifactHash !== 'string' || !artifactHash) {
        showToast('This leaderboard entry is missing deployment evidence.', 'error');
        return;
    }

    let directLive = false;
    let liveConfirmation = null;
    let message = `Stage strategy rank #${rank} for ${stage === 'LIVE' ? 'a live canary request' : 'paper review'}?`;
    if (stage === 'LIVE') {
        message += '\n\nWARNING: A live canary uses real money. The server will still require live execution to be explicitly unlocked, the bot to be paused, and the candidate to pass governance checks. Continue?';
    }
    if (!window.confirm(message)) return;

    if (stage === 'LIVE') {
        directLive = window.confirm('Skip the PAPER stage and deploy this candidate directly to LIVE?');
        if (directLive) {
            liveConfirmation = window.prompt('Type exactly: I UNDERSTAND LIVE RISK');
            if (liveConfirmation !== 'I UNDERSTAND LIVE RISK') {
                showToast('Direct LIVE cancelled: confirmation phrase did not match.', 'error');
                return;
            }
        }
    }

    try {
        const token = getLabToken();
        const response = await fetch('/api/strategy/promote', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(token ? { 'Authorization': `Bearer ${token}` } : {})
            },
            body: JSON.stringify({ rank, stage, candidate_id: candidateId, artifact_hash: artifactHash, direct_live: directLive, live_confirmation: liveConfirmation })
        });
        let result = {};
        try {
            result = await response.json();
        } catch (error) {
            result = {};
        }
        if (!response.ok) {
            showToast(typeof result.detail === 'string' ? result.detail : 'Deployment request was rejected.', 'error');
            return;
        }
        showToast(typeof result.message === 'string' ? result.message : `Strategy staged for ${stage}.`, 'success');
        await fetchLeaderboard();
    } catch (error) {
        console.error('Failed to promote strategy:', error);
        showToast('Error communicating with the server.', 'error');
    }
};

document.addEventListener('DOMContentLoaded', () => {
    const refreshButton = document.getElementById('refresh-lab-results');
    if (refreshButton) refreshButton.addEventListener('click', fetchLeaderboard);
});
