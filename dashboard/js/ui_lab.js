// ui_lab.js — AI Strategy Lab Progress Banner, Leaderboard Cards, and Command Copying

async function fetchLabProgress() {
    const banner = document.getElementById('lab-progress-banner');
    if (!banner) return;
    try {
        const res = await fetch('/api/lab/progress');
        const data = await res.json();
        const prog = data.progress || {};
        
        if (!prog.status || prog.status === 'idle') {
            banner.classList.add('hidden');
            return;
        }
        if (JSON.stringify(window.currentLabProgress) === JSON.stringify(prog)) return;
        window.currentLabProgress = prog;
        
        banner.classList.remove('hidden');
        const isInfinite = prog.total_trials === 0 || prog.total_trials === 'Infinite' || prog.total_trials === null;
        const pct = isInfinite ? 100 : Math.min(100, (prog.progress_pct || 0));
        const current = prog.current_trial || 0;
        const total = isInfinite ? '∞ (Infinite Mode)' : prog.total_trials;
        const totalDb = prog.total_db_trials || current;
        const bestScore = prog.best_score || 0;
        const bestName = prog.best_strategy_name || 'N/A';
        const elapsed = prog.elapsed_seconds || 0;
        const hours = Math.floor(elapsed / 3600);
        const mins = Math.floor((elapsed % 3600) / 60);
        const secs = elapsed % 60;
        const timeStr = hours > 0 ? `${hours}h ${mins}m ${secs}s` : `${mins}m ${secs}s`;
        
        const isRunning = prog.status === 'running' || prog.status === 'starting';
        
        banner.innerHTML = `
            <div class="glass-card p-6 md:p-8 rounded-3xl border ${isRunning ? 'border-neonCyan/50 bg-gradient-to-br from-slate-900/95 via-slate-900/90 to-cyan-950/30 shadow-[0_0_30px_rgba(0,240,255,0.15)]' : 'border-neonGreen/40 bg-gradient-to-br from-slate-900/95 to-emerald-950/20'} transition-all duration-500">
                <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-slate-800/80 pb-5 mb-6">
                    <div class="flex items-center gap-4">
                        <div class="w-12 h-12 rounded-2xl ${isRunning ? 'bg-neonCyan/20 border border-neonCyan/50 text-neonCyan animate-pulse' : 'bg-neonGreen/20 border border-neonGreen/50 text-neonGreen'} flex items-center justify-center text-2xl shadow-lg">
                            ${isRunning ? '⚡' : '✅'}
                        </div>
                        <div>
                            <div class="flex items-center gap-2">
                                <span class="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider ${isRunning ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40' : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'}">
                                    ${isRunning ? '🔥 AI LAB ACTIVE' : '✨ COMPLETED'}
                                </span>
                                <span class="text-xs text-slate-400 font-mono">⏱️ Elapsed: ${timeStr}</span>
                            </div>
                            <h2 class="text-lg md:text-xl font-extrabold text-white uppercase tracking-wide mt-1">
                                ${isRunning ? (isInfinite ? '⚡ INFINITE ALPHA EVOLUTION (Unlimited Mode)' : `🧬 EVOLVING ALPHA GENOME (80 Variables / 8 Systems)`) : `✅ ALPHA SYNTHESIS COMPLETED`}
                            </h2>
                        </div>
                    </div>
                    <div class="flex items-center gap-3 self-end md:self-center">
                        <div class="text-right">
                            <div class="text-xs text-slate-400 uppercase tracking-wider font-semibold">Session Progress</div>
                            <div class="text-lg font-black font-mono ${isRunning ? 'text-neonCyan' : 'text-neonGreen'}">
                                ${isRunning ? (isInfinite ? '∞ RUNNING' : `${current} / ${total}`) : `${current} Evaluated`}
                            </div>
                        </div>
                        <span class="px-4 py-2 rounded-2xl text-sm font-black font-mono shadow-inner ${isRunning ? 'bg-neonCyan/10 text-neonCyan border border-neonCyan/40' : 'bg-neonGreen/10 text-neonGreen border border-neonGreen/40'}">
                            ${isRunning ? (isInfinite ? '∞' : `${pct}%`) : '100%'}
                        </span>
                    </div>
                </div>
                <div class="mb-6">
                    <div class="flex justify-between text-xs text-slate-400 mb-2 font-semibold">
                        <span>🧪 Current Session: <strong class="text-white">${current}</strong> of <strong class="text-white">${total}</strong> trials</span>
                        <span>📚 All-Time DB Memory: <strong class="text-amber-400 font-mono">${totalDb}</strong> total trials</span>
                    </div>
                    <div class="w-full bg-slate-800/90 rounded-full h-4 overflow-hidden border border-slate-700/60 p-0.5 shadow-inner">
                        <div class="h-full rounded-full transition-all duration-700 ${isRunning ? 'bg-gradient-to-r from-cyan-400 via-blue-500 to-purple-500 shadow-[0_0_15px_rgba(0,240,255,0.8)]' : 'bg-gradient-to-r from-emerald-400 to-teal-500 shadow-[0_0_15px_rgba(16,185,129,0.8)]'}" style="width: ${pct}%"></div>
                    </div>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div class="bg-slate-800/50 border border-slate-700/60 rounded-2xl p-4 flex items-center justify-between shadow-sm hover:border-slate-600 transition-colors">
                        <div class="flex items-center gap-3.5">
                            <span class="text-3xl">🏆</span>
                            <div>
                                <div class="text-[11px] text-slate-400 uppercase font-bold tracking-wider">Best Blueprint Found So Far</div>
                                <div class="text-sm md:text-base font-extrabold text-neonCyan font-mono mt-0.5 truncate max-w-[240px] sm:max-w-[320px]">${escapeHTML(bestName)}</div>
                            </div>
                        </div>
                    </div>
                    <div class="bg-slate-800/50 border border-slate-700/60 rounded-2xl p-4 flex items-center justify-between shadow-sm hover:border-slate-600 transition-colors">
                        <div class="flex items-center gap-3.5">
                            <span class="text-3xl">🔥</span>
                            <div>
                                <div class="text-[11px] text-slate-400 uppercase font-bold tracking-wider">Top Fitness Score (Alpha Rating)</div>
                                <div class="text-lg md:text-xl font-black text-amber-400 font-mono mt-0.5">${bestScore} <span class="text-xs text-slate-400 font-normal">pts</span></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    } catch (err) {
        console.error('Failed to fetch lab progress:', err);
    }
}

async function fetchLeaderboard() {
    const container = document.getElementById('leaderboard-cards-container');
    if (!container) return;
    
    if (!window.currentLeaderboardStrategies || window.currentLeaderboardStrategies.length === 0) {
        container.innerHTML = `
            <div class="glass-card p-8 rounded-2xl text-center text-slate-400">
                <p class="animate-pulse text-neonCyan font-bold">🧬 Synthesizing & Fetching Alpha Leaderboard...</p>
            </div>
        `;
    }
    
    try {
        const res = await fetch('/api/lab/leaderboard');
        const data = await res.json();
        const strategies = data.strategies || [];
        
        if (JSON.stringify(window.currentLeaderboardStrategies) === JSON.stringify(strategies)) {
            return;
        }
        
        if (strategies.length === 0) {
            container.innerHTML = `
                <div class="glass-card p-8 rounded-2xl text-center text-slate-400 border border-slate-700">
                    <p class="text-base font-bold text-white mb-2">No Synthesized Strategies Found Yet</p>
                    <p class="text-xs">Run <code class="text-neonCyan">python bot_strategy_synthesizer.py</code> locally on your PC to evolve blueprints across 20 symbols!</p>
                </div>
            `;
            return;
        }
        
        container.innerHTML = "";
        window.currentLeaderboardStrategies = strategies;
        strategies.forEach((strat, idx) => {
            const rankBadge = idx === 0 ? "🏆 #1 ALPHA GENOME" : `#${strat.rank} BLUEPRINT`;
            const badgeColor = idx === 0 ? "bg-amber-500/20 text-amber-300 border-amber-500/50 shadow-[0_0_15px_rgba(245,158,11,0.3)]" : "bg-slate-800 text-slate-300 border-slate-700";
            
            const params = strat.parameters || {};
            const paramStr = JSON.stringify(params, null, 2);
            
            const card = document.createElement('div');
            card.className = `glass-card p-6 rounded-2xl border transition-all duration-300 hover:scale-[1.01] ${idx === 0 ? 'border-amber-500/40 bg-gradient-to-br from-amber-500/5 to-transparent' : 'border-slate-800 hover:border-slate-700'}`;
            
            card.innerHTML = `
                <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-slate-800/80 pb-4 mb-4">
                    <div>
                        <div class="flex items-center gap-3">
                            <span class="px-3 py-1 rounded-full text-xs font-extrabold border tracking-wider uppercase ${badgeColor}">
                                ${rankBadge}
                            </span>
                            <h3 class="text-lg font-extrabold text-white tracking-wide">${escapeHTML(strat.name || 'Blueprint')}</h3>
                        </div>
                    </div>
                    <button onclick="copyAICommandFromIndex(${idx})" class="px-4 py-2 rounded-xl bg-gradient-to-r from-neonCyan/20 to-blue-500/20 text-neonCyan font-bold text-xs uppercase tracking-widest border border-neonCyan/40 hover:bg-neonCyan/30 transition-all shadow-[0_0_10px_rgba(0,240,255,0.2)] flex items-center gap-2">
                        <span>📋</span> Copy AI Command
                    </button>
                </div>
                <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
                    <div class="bg-slate-900/60 p-3 rounded-xl border border-slate-800">
                        <span class="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">1M Return</span>
                        <span class="text-lg font-extrabold ${strat.net_profit_1m >= 0 ? 'text-neonGreen' : 'text-neonRed'}">${strat.net_profit_1m >= 0 ? '+' : ''}${strat.net_profit_1m}%</span>
                        <span class="text-[11px] block ${strat.net_profit_1m >= 0 ? 'text-neonGreen/80' : 'text-neonRed/80'} font-mono">(${strat.net_profit_1m_dollar !== undefined ? (strat.net_profit_1m_dollar >= 0 ? '+$' : '-$') + Math.abs(strat.net_profit_1m_dollar) : '$' + (strat.net_profit_1m * 10).toFixed(2)})</span>
                    </div>
                    <div class="bg-slate-900/60 p-3 rounded-xl border border-slate-800">
                        <span class="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">3M Return</span>
                        <span class="text-lg font-extrabold ${strat.net_profit_3m >= 0 ? 'text-neonGreen' : 'text-neonRed'}">${strat.net_profit_3m >= 0 ? '+' : ''}${strat.net_profit_3m}%</span>
                        <span class="text-[11px] block ${strat.net_profit_3m >= 0 ? 'text-neonGreen/80' : 'text-neonRed/80'} font-mono">(${strat.net_profit_3m_dollar !== undefined ? (strat.net_profit_3m_dollar >= 0 ? '+$' : '-$') + Math.abs(strat.net_profit_3m_dollar) : '$' + (strat.net_profit_3m * 10).toFixed(2)})</span>
                    </div>
                    <div class="bg-slate-900/60 p-3 rounded-xl border border-slate-800">
                        <span class="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">6M Return</span>
                        <span class="text-lg font-extrabold ${strat.net_profit_6m >= 0 ? 'text-neonGreen' : 'text-neonRed'}">${strat.net_profit_6m >= 0 ? '+' : ''}${strat.net_profit_6m}%</span>
                        <span class="text-[11px] block ${strat.net_profit_6m >= 0 ? 'text-neonGreen/80' : 'text-neonRed/80'} font-mono">(${strat.net_profit_6m_dollar !== undefined ? (strat.net_profit_6m_dollar >= 0 ? '+$' : '-$') + Math.abs(strat.net_profit_6m_dollar) : '$' + (strat.net_profit_6m * 10).toFixed(2)})</span>
                    </div>
                    <div class="bg-slate-900/60 p-3 rounded-xl border ${idx === 0 ? 'border-amber-500/30 bg-amber-500/10' : 'border-slate-800'}">
                        <span class="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">1Y Annualized</span>
                        <span class="text-xl font-extrabold ${strat.net_profit_1y >= 0 ? 'text-neonGreen text-glow-green' : 'text-neonRed'}">${strat.net_profit_1y >= 0 ? '+' : ''}${strat.net_profit_1y}%</span>
                        <span class="text-[11px] block ${strat.net_profit_1y >= 0 ? 'text-neonGreen text-glow-green' : 'text-neonRed'} font-mono font-bold">(${strat.net_profit_1y_dollar !== undefined ? (strat.net_profit_1y_dollar >= 0 ? '+$' : '-$') + Math.abs(strat.net_profit_1y_dollar) : '$' + (strat.net_profit_1y * 10).toFixed(2)})</span>
                    </div>
                </div>
                <div class="grid grid-cols-1 sm:grid-cols-4 gap-4 mb-4 text-xs bg-black/30 p-3 rounded-xl border border-slate-800/60">
                    <div><span class="text-slate-400 block text-[10px] uppercase font-bold">Win Rate:</span> <span class="text-white font-extrabold text-sm">${strat.win_rate_1y}%</span></div>
                    <div><span class="text-slate-400 block text-[10px] uppercase font-bold">Max Drawdown:</span> <span class="text-neonRed font-extrabold text-sm">-${strat.max_dd}%</span></div>
                    <div><span class="text-slate-400 block text-[10px] uppercase font-bold">Trade Activity:</span> <span class="text-neonCyan font-extrabold text-sm">${strat.total_trades_1y} ไม้</span> <span class="text-[10px] text-slate-400 block">(~${strat.avg_trades_month || (strat.total_trades_1y/12).toFixed(1)} ไม้/เดือน | ~${strat.avg_trades_day || (strat.total_trades_1y/365).toFixed(1)} ไม้/วัน)</span></div>
                    <div><span class="text-slate-400 block text-[10px] uppercase font-bold">Moonshots (>30%):</span> <span class="text-amber-400 font-extrabold text-sm">${strat.moonshots_1y} 🚀</span></div>
                </div>
                <div class="bg-black/40 rounded-xl p-3 border border-slate-800/80 font-mono text-xs text-slate-300">
                    <span class="text-slate-500 text-[10px] uppercase block mb-1 font-bold">🧬 Genome DNA Parameters:</span>
                    <pre class="overflow-x-auto text-[11px] text-neonCyan/90">${escapeHTML(paramStr)}</pre>
                </div>
            `;
            container.appendChild(card);
        });
    } catch (err) {
        container.innerHTML = `
            <div class="glass-card p-8 rounded-2xl text-center text-neonRed border border-neonRed/30">
                <p class="font-bold">Error loading Leaderboard: ${escapeHTML(err.message)}</p>
            </div>
        `;
    }
}

function copyAICommandFromIndex(idx) {
    if (!window.currentLeaderboardStrategies || !window.currentLeaderboardStrategies[idx]) return;
    const strat = window.currentLeaderboardStrategies[idx];
    const paramStr = JSON.stringify(strat.parameters || {}, null, 2);
    copyAICommand(strat.rank, strat.name || `Blueprint #${strat.rank}`, paramStr);
}

function copyAICommand(rank, name, paramStr) {
    const cmd = `Antigravity อัปเกรดระบบเทรดใน bot/strategy.py ให้ใช้กลยุทธ์ Blueprint #${rank} (${name}) ตามที่ห้องแล็บค้นพบเลย!\nพารามิเตอร์ DNA:\n${paramStr}`;
    navigator.clipboard.writeText(cmd).then(() => {
        alert("✅ Copied AI Upgrade Command to clipboard!\n\nPaste it into chat to have AI deploy Blueprint #" + rank + "!");
    }).catch(err => {
        prompt("Copy this AI Command:", cmd);
    });
}
