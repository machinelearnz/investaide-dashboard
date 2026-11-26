# -*- encoding: utf-8 -*-
"""
InvestAide Date-Anchored Event Signals Module
Extracts compact, deterministic event signals for Primary & Secondary securities:
1. Abnormal return shocks (1-day & 3-day excess return spikes on heavy volume)
2. Share count dynamics (sharp step changes and creeping dilution)
3. Structural regime signals (deepest drawdown, revenue vs PAT divergence, 36M range breakouts)
"""

import math
from datetime import datetime
import numpy as np
import pandas as pd


def _safe_float(val, decimals=2):
    """Safely converts scalar to rounded float or None."""
    if val is None or pd.isna(val):
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, decimals)
    except (ValueError, TypeError):
        return None


def compute_price_shock_events(price_series, benchmark_price_series, volume_series=None):
    """
    Detects single-day and 3-day abnormal return shocks over benchmark:
    - 1-Day: |e_t| >= max(3.5 * sigma_252d, 6.0%)
    - 3-Day: |e_3d,t| >= 10.0%
    - AND daily relative volume >= 2.5x.
    Clusters adjacent days within 15 calendar days, and retains Top 3 events ranked by |e| * rel_volume.
    """
    if price_series is None or price_series.empty or benchmark_price_series is None or benchmark_price_series.empty:
        return []

    # Common valid index alignment
    common_idx = price_series.dropna().index.intersection(benchmark_price_series.dropna().index)
    if len(common_idx) < 15:
        return []

    p_stock = price_series.loc[common_idx].astype(float)
    p_bench = benchmark_price_series.loc[common_idx].astype(float)

    # 1-day simple returns and excess return
    r_stock_1d = (p_stock / p_stock.shift(1)) - 1.0
    r_bench_1d = (p_bench / p_bench.shift(1)) - 1.0
    excess_1d = r_stock_1d - r_bench_1d

    # 3-day simple returns and excess return
    r_stock_3d = (p_stock / p_stock.shift(3)) - 1.0
    r_bench_3d = (p_bench / p_bench.shift(3)) - 1.0
    excess_3d = r_stock_3d - r_bench_3d

    # Trailing 252-day excess return standard deviation
    sigma_252d = excess_1d.rolling(window=252, min_periods=60).std()
    sample_std = float(excess_1d.dropna().std()) if not excess_1d.dropna().empty else 0.015
    sigma_252d = sigma_252d.fillna(sample_std).replace(0, sample_std)

    # Relative volume multiple (20D mean)
    if volume_series is not None and not volume_series.empty:
        v_stock = volume_series.reindex(common_idx).fillna(0).astype(float)
        mean_v20 = v_stock.rolling(window=20, min_periods=5).mean().replace(0, np.nan)
        rel_volume = (v_stock / mean_v20).replace([np.inf, -np.inf], np.nan).fillna(1.0)
    else:
        rel_volume = pd.Series(1.0, index=common_idx)

    n = len(common_idx)
    candidates = []

    for i in range(n):
        dt = common_idx[i]
        e1 = excess_1d.iloc[i]
        e3 = excess_3d.iloc[i]
        vm = float(rel_volume.iloc[i])
        sig = float(sigma_252d.iloc[i])

        if pd.isna(e1) or pd.isna(vm):
            continue

        th_1d = max(3.5 * sig, 0.06)
        cond_1d = (abs(e1) >= th_1d) and (vm >= 2.5)
        cond_3d = (not pd.isna(e3)) and (abs(e3) >= 0.10) and (vm >= 2.5)

        if cond_1d or cond_3d:
            if cond_1d and cond_3d:
                win = "1d" if abs(e1) >= (abs(e3) * 0.7) else "3d"
            elif cond_1d:
                win = "1d"
            else:
                win = "3d"

            stk_ret = float(r_stock_1d.iloc[i]) if win == "1d" else float(r_stock_3d.iloc[i])
            exc_ret = float(e1) if win == "1d" else float(e3)
            direction = "surge" if stk_ret >= 0 else "selloff"
            severity = abs(exc_ret) * vm

            candidates.append({
                'idx': i,
                'date': dt,
                'date_str': dt.strftime('%Y-%m-%d'),
                'window': win,
                'stock_return_pct': round(stk_ret * 100.0, 2),
                'excess_return_vs_benchmark_pct': round(exc_ret * 100.0, 2),
                'volume_multiple': round(vm, 2),
                'direction': direction,
                'severity': severity
            })

    if not candidates:
        return []

    # De-duplication: Iterative peak clustering within 15 calendar days
    cand_pool = candidates.copy()
    clustered_events = []
    while cand_pool:
        best = max(cand_pool, key=lambda x: x['severity'])
        clustered_events.append(best)
        peak_date = best['date']
        cand_pool = [c for c in cand_pool if abs((c['date'] - peak_date).days) > 15]

    clustered_events.sort(key=lambda x: x['severity'], reverse=True)
    top3 = clustered_events[:3]
    top3.sort(key=lambda x: x['date'])

    cleaned = []
    for ev in top3:
        cleaned.append({
            "date": ev['date_str'],
            "window": ev['window'],
            "stock_return_pct": _safe_float(ev['stock_return_pct']),
            "excess_return_vs_benchmark_pct": _safe_float(ev['excess_return_vs_benchmark_pct']),
            "volume_multiple": _safe_float(ev['volume_multiple']),
            "direction": ev['direction']
        })
    return cleaned


def compute_share_count_dynamics(annual_financials):
    """
    Evaluates share count evolution from annual_financials_4y:
    - Step Changes: Single-year |YoY%| >= 2.5% ("sharp_buyback" or "sharp_dilution")
    - Creeping Dilution: Increased in >= 3 consecutive years and cumulative increase >= 3.0%.
    """
    default_res = {
        "step_changes": [],
        "creeping_dilution": {
            "flagged": False,
            "cumulative_change_pct": 0.0,
            "consecutive_increase_years": 0
        }
    }

    if not annual_financials or not isinstance(annual_financials, list):
        return default_res

    # Parse and sort chronologically by year (e.g. FY 2023 -> FY 2024 -> FY 2025 -> FY 2026)
    valid_entries = []
    for f in annual_financials:
        if not isinstance(f, dict):
            continue
        fy_str = str(f.get('fiscal_year', ''))
        shares = f.get('basic_avg_shares_cr')
        if shares is not None and pd.notna(shares) and float(shares) > 0:
            # extract year number
            y_digits = ''.join([c for c in fy_str if c.isdigit()])
            fy_num = int(y_digits) if y_digits else 0
            valid_entries.append((fy_num, fy_str, float(shares)))

    valid_entries.sort(key=lambda x: x[0])
    if len(valid_entries) < 2:
        return default_res

    # 1. Step Changes
    step_changes = []
    for i in range(1, len(valid_entries)):
        prev_shares = valid_entries[i - 1][2]
        cur_shares = valid_entries[i][2]
        fy_label = valid_entries[i][1]

        if prev_shares > 0:
            yoy_change = ((cur_shares - prev_shares) / prev_shares) * 100.0
            if abs(yoy_change) >= 2.5:
                stype = "sharp_buyback" if yoy_change < 0 else "sharp_dilution"
                step_changes.append({
                    "fiscal_year": fy_label,
                    "yoy_change_pct": round(yoy_change, 2),
                    "type": stype
                })

    # 2. Creeping Dilution
    # Count maximum consecutive years of share increase
    consec_count = 0
    max_consec = 0
    for i in range(1, len(valid_entries)):
        if valid_entries[i][2] > valid_entries[i - 1][2]:
            consec_count += 1
            if consec_count > max_consec:
                max_consec = consec_count
        else:
            consec_count = 0

    earliest_shares = valid_entries[0][2]
    latest_shares = valid_entries[-1][2]
    cum_change = ((latest_shares - earliest_shares) / earliest_shares) * 100.0 if earliest_shares > 0 else 0.0

    flagged = (max_consec >= 3 or max_consec == (len(valid_entries) - 1)) and (cum_change >= 3.0)

    return {
        "step_changes": step_changes[:3],
        "creeping_dilution": {
            "flagged": bool(flagged),
            "cumulative_change_pct": round(cum_change, 2),
            "consecutive_increase_years": int(max_consec)
        }
    }


def compute_deepest_drawdown(price_series):
    """
    Computes running peak-to-trough drawdown over the analysis horizon:
    If max drawdown <= -20.0%, exports max_drawdown_pct, peak_date (YYYY-MM),
    trough_date (YYYY-MM), and recovered (bool). Otherwise returns None.
    """
    if price_series is None or price_series.dropna().empty or len(price_series.dropna()) < 10:
        return None

    p = price_series.dropna().astype(float)
    running_max = p.cummax()
    drawdown = (p - running_max) / running_max
    min_dd = float(drawdown.min())

    if min_dd > -0.20:
        return None

    trough_dt = drawdown.idxmin()
    peak_val = running_max.loc[trough_dt]
    # Peak date is latest date up to trough_dt where price == peak_val
    sub_peak = p.loc[:trough_dt]
    peak_matches = sub_peak[sub_peak >= peak_val * 0.9999]
    peak_dt = peak_matches.index[-1] if not peak_matches.empty else p.index[0]

    # Recovered check: Does price after trough_dt ever reach >= peak_val?
    sub_post = p.loc[trough_dt:]
    recovered = bool((sub_post >= peak_val).any())

    return {
        "max_drawdown_pct": round(min_dd * 100.0, 2),
        "peak_date": peak_dt.strftime("%Y-%m"),
        "trough_date": trough_dt.strftime("%Y-%m"),
        "recovered": recovered
    }


def compute_rev_vs_pat_divergence(annual_financials):
    """
    Computes 3-year Revenue CAGR and Net Income (PAT) CAGR:
    Flags if |PAT CAGR - Rev CAGR| >= 10.0 pp OR if they have opposite signs.
    Returns divergence details or None.
    """
    if not annual_financials or not isinstance(annual_financials, list) or len(annual_financials) < 2:
        return None

    valid = []
    for f in annual_financials:
        if not isinstance(f, dict):
            continue
        fy_str = str(f.get('fiscal_year', ''))
        y_digits = ''.join([c for c in fy_str if c.isdigit()])
        fy_num = int(y_digits) if y_digits else 0
        rev = f.get('total_revenue_cr')
        pat = f.get('net_income_cr')
        if rev is not None and pat is not None and pd.notna(rev) and pd.notna(pat) and float(rev) > 0:
            valid.append((fy_num, float(rev), float(pat)))

    valid.sort(key=lambda x: x[0])
    if len(valid) < 2:
        return None

    earliest = valid[0]
    latest = valid[-1]
    years_span = latest[0] - earliest[0]
    if years_span < 1:
        years_span = len(valid) - 1
    if years_span < 1:
        return None

    # Revenue CAGR
    rev_start, rev_end = earliest[1], latest[1]
    rev_cagr = (rev_end / rev_start) ** (1.0 / years_span) - 1.0

    # PAT CAGR
    pat_start, pat_end = earliest[2], latest[2]
    if pat_start > 0 and pat_end > 0:
        pat_cagr = (pat_end / pat_start) ** (1.0 / years_span) - 1.0
    else:
        pat_cagr = ((pat_end - pat_start) / abs(pat_start)) / years_span if pat_start != 0 else 0.0

    rev_cagr_pct = round(rev_cagr * 100.0, 2)
    pat_cagr_pct = round(pat_cagr * 100.0, 2)
    spread_pp = round(pat_cagr_pct - rev_cagr_pct, 2)

    opposite_signs = (rev_cagr_pct * pat_cagr_pct < 0) and (rev_cagr_pct != 0 or pat_cagr_pct != 0)
    triggered = (abs(spread_pp) >= 10.0) or opposite_signs

    if not triggered:
        return None

    signal = "operating_leverage_expansion" if spread_pp > 0 else "margin_compression_drag"

    return {
        "rev_cagr_3y_pct": rev_cagr_pct,
        "pat_cagr_3y_pct": pat_cagr_pct,
        "spread_pp": spread_pp,
        "signal": signal
    }


def compute_range_breakout_events(price_series, volume_series=None):
    """
    Detects if a stock traded within a tight 36-month range (high/low band within +/- 15% of 36M midpoint)
    and closed outside that band on monthly volume >= 2.0x its 12-month average.
    Returns up to Top 2 most recent breakouts/breakdowns.
    """
    if price_series is None or price_series.dropna().empty:
        return []

    p = price_series.dropna().astype(float)
    if volume_series is not None and not volume_series.dropna().empty:
        v = volume_series.reindex(p.index).fillna(0).astype(float)
    else:
        v = pd.Series(1.0, index=p.index)

    # Monthly resample
    m_close = p.resample('ME').last().dropna()
    m_vol = v.resample('ME').sum()

    n = len(m_close)
    if n < 37:
        return []

    breakout_events = []
    for i in range(36, n):
        dt = m_close.index[i]
        cur_p = float(m_close.iloc[i])
        cur_v = float(m_vol.iloc[i])

        prior_36 = m_close.iloc[i - 36: i]
        h36 = float(prior_36.max())
        l36 = float(prior_36.min())
        midpoint = (h36 + l36) / 2.0

        if midpoint <= 0:
            continue

        band_high = (h36 - midpoint) / midpoint
        band_low = (midpoint - l36) / midpoint
        is_tight = (band_high <= 0.15) and (band_low <= 0.15)

        if not is_tight:
            continue

        prior_12_v = m_vol.iloc[max(0, i - 12): i]
        mean_v12 = float(prior_12_v.mean()) if not prior_12_v.empty else 1.0
        vol_mult = (cur_v / mean_v12) if mean_v12 > 0 else 1.0

        is_breakout = (cur_p > h36)
        is_breakdown = (cur_p < l36)

        if (is_breakout or is_breakdown) and (vol_mult >= 2.0):
            breakout_events.append({
                'month': dt.strftime('%Y-%m'),
                'date': dt,
                'direction': 'breakout' if is_breakout else 'breakdown',
                'prior_range_months': 36,
                'volume_multiple': round(vol_mult, 2)
            })

    if not breakout_events:
        return []

    # De-duplicate adjacent months within 6 months
    clustered = []
    for ev in breakout_events:
        if not clustered:
            clustered.append(ev)
        else:
            prev_dt = clustered[-1]['date']
            if abs((ev['date'] - prev_dt).days) > 180:
                clustered.append(ev)
            elif ev['volume_multiple'] > clustered[-1]['volume_multiple']:
                clustered[-1] = ev

    # Retain up to Top 2 most recent
    most_recent = clustered[-2:]
    cleaned = []
    for ev in most_recent:
        cleaned.append({
            "month": ev['month'],
            "direction": ev['direction'],
            "prior_range_months": ev['prior_range_months'],
            "volume_multiple": _safe_float(ev['volume_multiple'])
        })
    return cleaned


def build_security_event_signals(price_series, benchmark_price_series, volume_series, annual_financials):
    """
    Constructs the complete event_signals block for a single security.
    """
    price_shocks = compute_price_shock_events(price_series, benchmark_price_series, volume_series)
    share_dynamics = compute_share_count_dynamics(annual_financials)
    deepest_dd = compute_deepest_drawdown(price_series)
    rev_pat_div = compute_rev_vs_pat_divergence(annual_financials)
    range_breakouts = compute_range_breakout_events(price_series, volume_series)

    return {
        "price_shock_events": price_shocks,
        "share_count_dynamics": share_dynamics,
        "deepest_drawdown": deepest_dd,
        "rev_vs_pat_divergence": rev_pat_div,
        "range_breakout_events": range_breakouts
    }


def build_event_signals_block(prices_df, volume_df, benchmark, primary_ticker, secondary_ticker=None,
                              fin_primary=None, fin_secondary=None, has_secondary=False):
    """
    Constructs the top-level event_signals dictionary for primary and secondary (or null).
    """
    if prices_df is None or prices_df.empty or len(prices_df.columns) < 2:
        return {
            "primary": None,
            "secondary": None
        }

    b_col = benchmark if benchmark in prices_df.columns else prices_df.columns[0]
    p1_col = primary_ticker if primary_ticker in prices_df.columns else prices_df.columns[1]

    # Volume series
    v1_series = None
    if volume_df is not None and not volume_df.empty:
        if primary_ticker in volume_df.columns:
            v1_series = volume_df[primary_ticker]
        elif len(volume_df.columns) >= 2:
            v1_series = volume_df[volume_df.columns[1]]

    prim_signals = build_security_event_signals(
        prices_df[p1_col],
        prices_df[b_col],
        v1_series,
        fin_primary
    )

    sec_signals = None
    if has_secondary and len(prices_df.columns) >= 3 and prices_df.columns[2] != 'Phase':
        p2_col = secondary_ticker if secondary_ticker in prices_df.columns else prices_df.columns[2]
        v2_series = None
        if volume_df is not None and not volume_df.empty:
            if secondary_ticker in volume_df.columns:
                v2_series = volume_df[secondary_ticker]
            elif len(volume_df.columns) >= 3:
                v2_series = volume_df[volume_df.columns[2]]

        sec_signals = build_security_event_signals(
            prices_df[p2_col],
            prices_df[b_col],
            v2_series,
            fin_secondary
        )

    return {
        "primary": prim_signals,
        "secondary": sec_signals
    }
