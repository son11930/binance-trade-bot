"""
fitness.py — The 4-Pillar Practical Fitness Framework grading and vectorized batch calculation.
"""
import numpy as np
from typing import Dict, List, Any
from .config import GENOME_PARAM_ORDER, N_GENOME_PARAMS, _STRAT_MAP_MB, _MACRO_MAP_MB
from bot.strategy_contract import canonical_macro_regime, strategy_id

# Qualification is deliberately stricter than search ranking.  A candidate
# must have enough independent OOS observations to make promotion meaningful.
MIN_TOTAL_TRADES = 100
MIN_OOS_TRADES = 30
MIN_OOS_PROFIT_FACTOR = 1.10
MAX_OOS_DRAWDOWN = 15.0

def _apply_four_pillar_fitness(res: Dict[str, Any], h_names: List[str]) -> Dict[str, Any]:
    """Applies the 4-Pillar Practical Fitness Framework to an evaluated results dictionary."""
    res = dict(res)
    FEE_PER_TRADE_PCT = 0.10
    horizon_divisors = {"1y": 1.0, "6m": 2.0, "3m": 4.0, "1m": 12.0}
    
    total_trades_1y = res.get("total_trades_1y", 0)
    win_rate = res.get("win_rate_1y", 0.0)
    max_dd = abs(float(res.get("max_dd", 0.0) or 0.0))
    
    # ── 0. Average Profit per Trade Metric ──
    net_p_1y = res.get("net_profit_1y", 0.0)
    net_p_1y_dollar = res.get("net_profit_1y_dollar", 0.0)
    if total_trades_1y > 0:
        res["avg_profit_per_trade_pct"] = round(net_p_1y / total_trades_1y, 3)
        res["avg_profit_per_trade_dollar"] = round(net_p_1y_dollar / total_trades_1y, 2)
    else:
        res["avg_profit_per_trade_pct"] = 0.0
        res["avg_profit_per_trade_dollar"] = 0.0

    # ── 1. Real-World Fee & Slippage Drag (Already deducted in simulation kernels: 0.15% round-trip per trade) & Calmar Profit Scaling ──
    total_profit_live = 0.0
    for h in h_names:
        raw_p = res.get(f"net_profit_{h}", 0.0)
        total_profit_live += raw_p

    # Calmar-Ratio Profit Scaling: Slash profit score if Max Drawdown exceeds 25% safe threshold
    dd_factor = min(1.0, (25.0 / max(1.0, max_dd)) ** 1.5)
    total_profit_live = min(total_profit_live, 40000.0) * dd_factor
    all_horizon_bonus = 1000.0 if (res.get("net_profit_1y", 0.0) >= 3.0 and res.get("net_profit_6m", 0.0) >= 1.5 and res.get("net_profit_3m", 0.0) >= 0.7 and res.get("net_profit_1m", 0.0) >= 0.2) else 0.0
    penalty_profit = -2500.0 if (res.get("net_profit_1y", 0.0) <= 0.0 and total_trades_1y > 0) else 0.0
    profit_score = total_profit_live * 3.0

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

    # ── 4. Final Composite Practical Fitness Score (Quadratic Drawdown Punishment) ──
    win_score = win_rate * 3.0
    dd_penalty = (max_dd * 2.5) + (max(0.0, max_dd - 30.0) ** 2 * 15.0)
    res["fitness_score"] = round(profit_score + all_horizon_bonus + win_score + score_trades - dd_penalty + penalty_win + penalty_profit, 2)
    return res

def _pack_genomes_to_flat(genome_batch: List[Dict[str, Any]]) -> np.ndarray:
    """
    Convert a list of genome dicts into a [n_genomes, N_GENOME_PARAMS=66] float32 matrix.
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
                mat[gi, pi] = float(strategy_id(gn.get("strategy_type", "rsi_sniper")))
            elif p_name == "macro_regime_filter":
                mat[gi, pi] = float(_MACRO_MAP_MB[canonical_macro_regime(gn.get("macro_regime_filter", "sma200_only"))])
            elif p_name == "kelly_fraction_cap":
                mat[gi, pi] = max(0.15, min(0.40, float(gn.get(p_name, 0.25))))
            else:
                mat[gi, pi] = float(gn.get(p_name, 0.0))
    return mat

def _compute_fitness_from_matrix(raw_gi: np.ndarray, h_names: List[str]) -> Dict[str, Any]:
    """Legacy individual compute removed as we fully rely on _vectorized_batch_compute_fitness"""
    pass

def _vectorized_batch_compute_fitness(raw: np.ndarray, n_g: int) -> List[Dict[str, Any]]:
    """
    Ultra-fast vectorized NumPy calculation of 4-Pillar Practical Fitness across ALL genomes in a batch.
    Replaces the slow 4096x Python loop.
    raw shape is [n_g, n_h, 4]
    """
    raw = np.nan_to_num(np.asarray(raw), nan=0.0, posinf=0.0, neginf=0.0)
    is_p_1m = raw[:, 0, 0]
    is_p_3m = raw[:, 1, 0]
    is_p_6m = raw[:, 2, 0]
    is_p_1y = raw[:, 3, 0]
    
    oos_p_1m = raw[:, 0, 8]
    oos_p_3m = raw[:, 1, 8]
    oos_p_6m = raw[:, 2, 8]
    oos_p_1y = raw[:, 3, 8]

    avg_p_1m = is_p_1m + oos_p_1m
    avg_p_3m = is_p_3m + oos_p_3m
    avg_p_6m = is_p_6m + oos_p_6m
    avg_p_1y = is_p_1y + oos_p_1y

    is_trades_1y = raw[:, 3, 3]
    oos_trades_1y = raw[:, 3, 11]
    total_trades_1y = is_trades_1y + oos_trades_1y

    is_win_rate_1y = raw[:, 3, 1]
    oos_win_rate_1y = raw[:, 3, 9]
    win_rate_1y = np.where(total_trades_1y > 0, 
                           (is_win_rate_1y * is_trades_1y + oos_win_rate_1y * oos_trades_1y) / np.maximum(1.0, total_trades_1y),
                           0.0)

    is_max_dd_1y = raw[:, 3, 2]
    oos_max_dd_1y = raw[:, 3, 10]
    max_dd_1y = np.maximum(is_max_dd_1y, oos_max_dd_1y)
    
    is_gross_profit_1y = raw[:, 3, 4]
    oos_gross_profit_1y = raw[:, 3, 12]
    is_gross_loss_1y = raw[:, 3, 5]
    oos_gross_loss_1y = raw[:, 3, 13]
    oos_trades_1y = oos_trades_1y.astype(np.float32, copy=False)
    is_max_streak_1y = raw[:, 3, 6]
    oos_max_streak_1y = raw[:, 3, 14]
    
    total_gross_profit_1y = is_gross_profit_1y + oos_gross_profit_1y
    total_gross_loss_1y = is_gross_loss_1y + oos_gross_loss_1y
    with np.errstate(divide='ignore', invalid='ignore'):
        pf_1y = np.where(total_gross_loss_1y > 0.0, total_gross_profit_1y / total_gross_loss_1y, np.where(total_gross_profit_1y > 0.0, 99.0, 0.0))
        oos_pf_1y = np.where(oos_gross_loss_1y > 0.0, oos_gross_profit_1y / oos_gross_loss_1y, np.where(oos_gross_profit_1y > 0.0, 99.0, 0.0))
        oos_expectancy = np.where(oos_trades_1y > 0, (oos_gross_profit_1y - oos_gross_loss_1y) / oos_trades_1y, 0.0)
    
    moonshots_1y = np.where(avg_p_1y > 30.0, 1, 0)

    # ── Pillar A: Fee & Slippage Drag & Calmar Profit Scaling ──
    total_profit_live = avg_p_1y + avg_p_6m + avg_p_3m + avg_p_1m

    # Calmar-Ratio Profit Scaling: Slash profit score if Max Drawdown exceeds 25% safe threshold
    dd_factor = np.minimum(1.0, (25.0 / np.maximum(1.0, max_dd_1y)) ** 1.5)
    total_profit_live = np.minimum(total_profit_live, 40000.0) * dd_factor
    all_horizon_bonus = np.where((avg_p_1y >= 3.0) & (avg_p_6m >= 1.5) & (avg_p_3m >= 0.7) & (avg_p_1m >= 0.2), 1000.0, 0.0)
    penalty_profit = np.where((avg_p_1y <= 0.0) & (total_trades_1y > 0), -2500.0, 0.0)
    profit_score = total_profit_live * 3.0

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

    # ── Pillar D: Final Composite Practical Fitness Score (Quadratic Drawdown Punishment) ──
    win_score = win_rate_1y * 3.0
    dd_penalty = (max_dd_1y * 2.5) + (np.maximum(0.0, max_dd_1y - 30.0) ** 2 * 15.0)
    
    # ── Pillar E: Walk-Forward Validation (WFA) Penalty ──
    is_ann_p = is_p_1y / 0.7
    oos_ann_p = oos_p_1y / 0.3
    with np.errstate(divide='ignore', invalid='ignore'):
        wfa_ratio = np.where(is_ann_p > 0.0, oos_ann_p / is_ann_p, 0.0)
    
    wfa_penalty = np.where(
        (is_ann_p > 10.0) & (wfa_ratio < 0.5),
        -5000.0 * (0.5 - wfa_ratio),
        0.0
    )
    wfa_penalty = np.where(
        (is_ann_p > 10.0) & (oos_ann_p < 0.0),
        -5000.0 + (oos_ann_p * 100.0), # oos_ann_p is negative, so this increases penalty proportionally
        wfa_penalty
    )

    # ── Pillar F: Phase 4 Hard Gates (PF, Expectancy, OOS Max DD) ──
    hard_gate_penalty = np.zeros(n_g, dtype=np.float32)
    # Hard Gate 1: OOS PF < 1.10
    hard_gate_penalty = np.where((oos_trades_1y > 0) & (oos_pf_1y < 1.10), -5000.0 * (1.10 - oos_pf_1y), hard_gate_penalty)
    # Hard Gate 2: OOS Expectancy < 0
    hard_gate_penalty = np.where((oos_trades_1y > 0) & (oos_expectancy < 0.0), hard_gate_penalty - 5000.0 * (0.0 - oos_expectancy), hard_gate_penalty)
    # Hard Gate 3: OOS Max DD > 15%
    hard_gate_penalty = np.where(oos_max_dd_1y > 15.0, hard_gate_penalty - 1000.0 * (oos_max_dd_1y - 15.0), hard_gate_penalty)

    fitness_arr = np.round(profit_score + all_horizon_bonus + win_score + score_trades - dd_penalty + penalty_win + penalty_profit + wfa_penalty + hard_gate_penalty, 2)

    results = []
    for gi in range(n_g):
        t = int(total_trades_1y[gi])
        np_1y = float(avg_p_1y[gi])
        np_1y_dollar = np_1y * 10.0
        avg_trade_pct = round(np_1y / t, 3) if t > 0 else 0.0
        avg_trade_dollar = round(np_1y_dollar / t, 2) if t > 0 else 0.0
        results.append({
            "net_profit_1y": round(np_1y, 2),
            "net_profit_1y_dollar": round(np_1y_dollar, 2),
            "is_profit_1y": round(float(is_p_1y[gi]), 2),
            "oos_profit_1y": round(float(oos_p_1y[gi]), 2),
            "avg_profit_per_trade_pct": avg_trade_pct,
            "avg_profit_per_trade_dollar": avg_trade_dollar,
            "net_profit_6m": round(float(avg_p_6m[gi]), 2),
            "net_profit_6m_dollar": round(float(avg_p_6m[gi]) * 10.0, 2),
            "net_profit_3m": round(float(avg_p_3m[gi]), 2),
            "net_profit_3m_dollar": round(float(avg_p_3m[gi]) * 10.0, 2),
            "net_profit_1m": round(float(avg_p_1m[gi]), 2),
            "net_profit_1m_dollar": round(float(avg_p_1m[gi]) * 10.0, 2),
            "win_rate_1y": round(float(win_rate_1y[gi]), 2),
            "max_dd": round(float(max_dd_1y[gi]), 2),
            "total_trades_1y": t,
            "is_trades_1y": int(is_trades_1y[gi]),
            "oos_trades_1y": int(oos_trades_1y[gi]),
            "is_max_dd": round(float(is_max_dd_1y[gi]), 2),
            "oos_max_dd": round(float(oos_max_dd_1y[gi]), 2),
            "moonshots_1y": int(moonshots_1y[gi]),
            "avg_trades_month": round(t / 12.0, 1),
            "avg_trades_day": round(t / 365.0, 1),
            "profit_factor": round(float(pf_1y[gi]), 2),
            "oos_profit_factor": round(float(oos_pf_1y[gi]), 2),
            "oos_expectancy": round(float(oos_expectancy[gi]), 3),
            "fitness_score": float(fitness_arr[gi])
        })
    return results
