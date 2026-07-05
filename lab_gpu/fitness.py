"""
fitness.py — The 4-Pillar Practical Fitness Framework grading and vectorized batch calculation.
"""
import numpy as np
from typing import Dict, List, Any
from .config import GENOME_PARAM_ORDER, N_GENOME_PARAMS, _STRAT_MAP_MB, _MACRO_MAP_MB

def _apply_four_pillar_fitness(res: Dict[str, Any], h_names: List[str]) -> Dict[str, Any]:
    """Applies the 4-Pillar Practical Fitness Framework to an evaluated results dictionary."""
    FEE_PER_TRADE_PCT = 0.10
    horizon_divisors = {"1y": 1.0, "6m": 2.0, "3m": 4.0, "1m": 12.0}
    
    total_trades_1y = res.get("total_trades_1y", 0)
    win_rate = res.get("win_rate_1y", 0.0)
    
    # ── 1. Real-World Fee & Slippage Drag (0.10% per trade round-trip) ──
    total_profit_live = 0.0
    for h in h_names:
        raw_p = res.get(f"net_profit_{h}", 0.0)
        t_count = total_trades_1y / horizon_divisors.get(h, 1.0)
        live_p = raw_p - (t_count * FEE_PER_TRADE_PCT)
        total_profit_live += live_p

    total_profit_live = min(total_profit_live, 40000.0)
    all_horizon_bonus = 500.0 if all(res.get(f"net_profit_{h}", 0.0) > 0 for h in h_names) else 0.0

    # ── 2. Win Rate Hurdle & Sigmoidal Penalty (Target >= 38%) ──
    WIN_TARGET = 38.0
    if win_rate < 28.0 and total_trades_1y > 0:
        penalty_win = -9999.0  # Hard kill-switch for impractical win rates < 28%
    elif win_rate < WIN_TARGET and total_trades_1y > 0:
        penalty_win = -1500.0 * ((WIN_TARGET - win_rate) / WIN_TARGET) ** 2
    else:
        penalty_win = 0.0

    # ── 3. Trade Frequency Band & Overtrading Punishment ──
    # Target: 500 to 2500 trades/year across all 20 symbols combined (~1.4 to ~6.8 trades/day total)
    if total_trades_1y < 365:
        score_trades = -3000.0 * ((365.0 - total_trades_1y) / 365.0)
    elif total_trades_1y < 500:
        score_trades = -500.0 * ((500.0 - total_trades_1y) / 135.0)
    elif total_trades_1y <= 2500:
        score_trades = 100.0
    else:
        score_trades = 100.0 - 2.0 * (total_trades_1y - 2500.0)

    # ── 4. Final Composite Practical Fitness Score ──
    win_score = win_rate * 3.0
    dd_penalty = res.get("max_dd", 0.0) * 2.5
    res["fitness_score"] = round(total_profit_live + all_horizon_bonus + win_score + score_trades - dd_penalty + penalty_win, 2)
    return res

def _pack_genomes_to_flat(genome_batch: List[Dict[str, Any]]) -> np.ndarray:
    """
    Convert a list of genome dicts into a [n_genomes, N_GENOME_PARAMS=29] float32 matrix.
    Parameter order matches GENOME_PARAM_ORDER and the mega-kernel's indexing.
    """
    n = len(genome_batch)
    mat = np.zeros((n, N_GENOME_PARAMS), dtype=np.float32)
    for gi, gn in enumerate(genome_batch):
        for pi, p_name in enumerate(GENOME_PARAM_ORDER):
            if p_name == "use_dual_trend":
                mat[gi, pi] = 1.0 if gn.get(p_name, True) else 0.0
            elif p_name == "require_green_candle":
                mat[gi, pi] = 1.0 if gn.get(p_name, False) else 0.0
            elif p_name == "strategy_type":
                mat[gi, pi] = float(_STRAT_MAP_MB.get(gn.get("strategy_type", "rsi_sniper"), 0))
            elif p_name == "macro_regime_filter":
                mat[gi, pi] = float(_MACRO_MAP_MB.get(gn.get("macro_regime_filter", "sma200_only"), 0))
            else:
                mat[gi, pi] = float(gn.get(p_name, 0.0))
    return mat

def _compute_fitness_from_matrix(raw_gi: np.ndarray, h_names: List[str]) -> Dict[str, Any]:
    """
    Aggregate one genome's raw GPU output matrix into a fitness dict.
    raw_gi shape: [n_symbols, n_horizons, 4]  (4 = profit, winrate, maxdd, trades)
    """
    n_s, n_h, _ = raw_gi.shape
    res: Dict[str, Any] = {}
    total_trades_1y = 0
    win_rate_1y     = 0.0
    max_dd_all      = 0.0
    moonshots       = 0

    for hi, h_name in enumerate(h_names):
        profits = []
        for si in range(n_s):
            profit = float(raw_gi[si, hi, 0])
            if raw_gi[si, hi, 3] == 0.0 and raw_gi[si, hi, 0] == 0.0:
                continue
            profits.append(profit)
            if h_name == "1y":
                trades = int(raw_gi[si, hi, 3])
                wins   = int(round(raw_gi[si, hi, 1] * trades / 100.0)) if trades > 0 else 0
                dd     = float(raw_gi[si, hi, 2])
                total_trades_1y += trades
                if dd > max_dd_all:
                    max_dd_all = dd
                if profit > 30.0:
                    moonshots += 1

        avg = float(np.mean(profits)) if profits else 0.0
        res[f"net_profit_{h_name}"]        = round(avg, 2)
        res[f"net_profit_{h_name}_dollar"] = round(avg * 10.0, 2)

        if h_name == "1y" and total_trades_1y > 0:
            total_wins = 0
            for si in range(n_s):
                t = int(raw_gi[si, hi, 3])
                if t > 0:
                    total_wins += int(round(raw_gi[si, hi, 1] * t / 100.0))
            win_rate_1y = (total_wins / total_trades_1y * 100.0) if total_trades_1y > 0 else 0.0

    res["win_rate_1y"]      = round(win_rate_1y, 2)
    res["max_dd"]           = round(max_dd_all, 2)
    res["total_trades_1y"]  = total_trades_1y
    res["moonshots_1y"]     = moonshots
    res["avg_trades_month"] = round(total_trades_1y / 12.0, 1)
    res["avg_trades_day"]   = round(total_trades_1y / 365.0, 1)

    return _apply_four_pillar_fitness(res, h_names)

def _vectorized_batch_compute_fitness(raw: np.ndarray, n_g: int, n_s: int) -> List[Dict[str, Any]]:
    """
    Ultra-fast vectorized NumPy calculation of 4-Pillar Practical Fitness across ALL genomes in a batch.
    Replaces the slow 4096x Python loop over _compute_fitness_from_matrix (1000x CPU speedup).
    """
    avg_p = []
    for hi in range(4):
        p_mat = raw[:, :, hi, 0]
        t_mat = raw[:, :, hi, 3]
        valid_mask = (t_mat > 0.0) | (p_mat != 0.0)
        valid_counts = np.sum(valid_mask, axis=1)
        sum_p = np.sum(np.where(valid_mask, p_mat, 0.0), axis=1)
        avg_p.append(np.where(valid_counts > 0, sum_p / valid_counts, 0.0))

    avg_p_1m, avg_p_3m, avg_p_6m, avg_p_1y = avg_p[0], avg_p[1], avg_p[2], avg_p[3]

    total_trades_1y = np.sum(raw[:, :, 3, 3], axis=1)
    wins_mat = np.round(raw[:, :, 3, 1] * raw[:, :, 3, 3] / 100.0)
    total_wins_1y = np.sum(wins_mat, axis=1)
    win_rate_1y = np.where(total_trades_1y > 0, (total_wins_1y / total_trades_1y) * 100.0, 0.0)
    max_dd_1y = np.max(raw[:, :, 3, 2], axis=1)
    moonshots_1y = np.sum(raw[:, :, 3, 0] > 30.0, axis=1)

    # ── Pillar A: Fee & Slippage Drag ──
    FEE = 0.10
    live_p_1y = avg_p_1y - (total_trades_1y / 1.0 * FEE)
    live_p_6m = avg_p_6m - (total_trades_1y / 2.0 * FEE)
    live_p_3m = avg_p_3m - (total_trades_1y / 4.0 * FEE)
    live_p_1m = avg_p_1m - (total_trades_1y / 12.0 * FEE)
    total_profit_live = live_p_1y + live_p_6m + live_p_3m + live_p_1m
    total_profit_live = np.minimum(total_profit_live, 40000.0)
    all_horizon_bonus = np.where((avg_p_1y > 0) & (avg_p_6m > 0) & (avg_p_3m > 0) & (avg_p_1m > 0), 500.0, 0.0)

    # ── Pillar B: Win Rate Hurdle ──
    WIN_TARGET = 38.0
    penalty_win = np.zeros(n_g, dtype=np.float32)
    kill_mask = (win_rate_1y < 28.0) & (total_trades_1y > 0)
    hurdle_mask = (win_rate_1y >= 28.0) & (win_rate_1y < WIN_TARGET) & (total_trades_1y > 0)
    penalty_win[kill_mask] = -9999.0
    penalty_win[hurdle_mask] = -1500.0 * ((WIN_TARGET - win_rate_1y[hurdle_mask]) / WIN_TARGET) ** 2

    # ── Pillar C: Trade Frequency Band (500 to 2500) ──
    score_trades = np.zeros(n_g, dtype=np.float32)
    kill_under_mask = total_trades_1y < 365
    under_mask = (total_trades_1y >= 365) & (total_trades_1y < 500)
    sweet_mask = (total_trades_1y >= 500) & (total_trades_1y <= 2500)
    over_mask = total_trades_1y > 2500
    score_trades[kill_under_mask] = -3000.0 * ((365.0 - total_trades_1y[kill_under_mask]) / 365.0)
    score_trades[under_mask] = -500.0 * ((500.0 - total_trades_1y[under_mask]) / 135.0)
    score_trades[sweet_mask] = 100.0
    score_trades[over_mask] = 100.0 - 2.0 * (total_trades_1y[over_mask] - 2500.0)

    # ── Pillar D: Final Composite Practical Fitness Score ──
    win_score = win_rate_1y * 3.0
    dd_penalty = max_dd_1y * 2.5
    fitness_arr = np.round(total_profit_live + all_horizon_bonus + win_score + score_trades - dd_penalty + penalty_win, 2)

    results = []
    for gi in range(n_g):
        t = int(total_trades_1y[gi])
        results.append({
            "net_profit_1y": round(float(avg_p_1y[gi]), 2),
            "net_profit_1y_dollar": round(float(avg_p_1y[gi]) * 10.0, 2),
            "net_profit_6m": round(float(avg_p_6m[gi]), 2),
            "net_profit_6m_dollar": round(float(avg_p_6m[gi]) * 10.0, 2),
            "net_profit_3m": round(float(avg_p_3m[gi]), 2),
            "net_profit_3m_dollar": round(float(avg_p_3m[gi]) * 10.0, 2),
            "net_profit_1m": round(float(avg_p_1m[gi]), 2),
            "net_profit_1m_dollar": round(float(avg_p_1m[gi]) * 10.0, 2),
            "win_rate_1y": round(float(win_rate_1y[gi]), 2),
            "max_dd": round(float(max_dd_1y[gi]), 2),
            "total_trades_1y": t,
            "moonshots_1y": int(moonshots_1y[gi]),
            "avg_trades_month": round(t / 12.0, 1),
            "avg_trades_day": round(t / 365.0, 1),
            "fitness_score": float(fitness_arr[gi])
        })
    return results
