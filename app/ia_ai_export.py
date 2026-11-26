# -*- encoding: utf-8 -*-
"""
InvestAide AI Context & Analysis JSON Exporter (v1.0)
Prepares compact, structured, LLM-ready quantitative payloads (schema_version: "1.0")
from pre-computed Relative Value report data with ZERO extra data fetches.
Supports both Pair Mode and Single-Security (Solo) Mode.
"""

import math
from datetime import datetime, timezone, date
import numpy as np
import pandas as pd
from . import ia_stockcharts as sc


def safe_num(val, decimals=2):
    """Safely converts scalar to float, rounding or returning None on NaN/Inf/None."""
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except Exception:
        pass
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, decimals)
    except (ValueError, TypeError):
        return None


def clean_for_json(obj):
    """Recursively converts all data structures and scalars into safe JSON-compliant types."""
    if obj is None:
        return None
    if isinstance(obj, (float, np.floating)):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return round(float(obj), 4) if (abs(obj) < 1e-4 and obj != 0) else round(float(obj), 2)
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (pd.Timestamp, date, datetime)):
        return obj.strftime("%Y-%m-%d")
    if isinstance(obj, pd.Series):
        return clean_for_json(obj.to_dict())
    if isinstance(obj, (list, tuple, np.ndarray)):
        return [clean_for_json(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): clean_for_json(v) for k, v in obj.items()}
    try:
        if pd.isna(obj):
            return None
    except Exception:
        pass
    return str(obj)


def _prepare_ttm_df(df, s_date=None, e_date=None):
    """Filters EPS dataframe to positive TTM EPS rows within analysis horizon."""
    if df is None or df.empty or 'TTM EPS' not in df.columns:
        return pd.DataFrame()
    q = df.dropna(subset=['TTM EPS']).sort_values('Date', ascending=True).copy()
    q = q[q['TTM EPS'] > 0]
    if s_date:
        try:
            s_dt = pd.to_datetime(s_date).normalize()
            filtered = q[q['Date'] >= s_dt]
            if not filtered.empty:
                q = filtered
        except Exception:
            pass
    if e_date:
        try:
            e_dt = pd.to_datetime(e_date).normalize()
            filtered = q[q['Date'] <= e_dt]
            if not filtered.empty:
                q = filtered
        except Exception:
            pass
    return q


def extract_valuation_snapshot(ticker_symbol, pe_data=None):
    """Extracts valuation metrics including historical_median_pe from expectations & valuation cache."""
    if not ticker_symbol or str(ticker_symbol).strip().upper() in ["NA", "NONE", "", "NULL"]:
        return None

    raw = getattr(sc, '_LAST_SECURITY_EXPECTATIONS', {}).get(ticker_symbol)
    if not raw:
        raw_sym = str(ticker_symbol).replace(".NS", "").replace(".BO", "")
        for k, v in getattr(sc, '_LAST_SECURITY_EXPECTATIONS', {}).items():
            if str(k).replace(".NS", "").replace(".BO", "") == raw_sym:
                raw = v
                break

    # Historical Median P/E
    hist_med_pe = None
    if pe_data and isinstance(pe_data, dict):
        hist_med_pe = safe_num(pe_data.get('median_pe'))
    if hist_med_pe is None:
        sec_d = getattr(sc, '_LAST_SECURITY_DATA', {}).get(ticker_symbol, {})
        p_d = sec_d.get('pe_data')
        if p_d and isinstance(p_d, dict):
            hist_med_pe = safe_num(p_d.get('median_pe'))

    if not raw:
        sec_d = getattr(sc, '_LAST_SECURITY_DATA', {}).get(ticker_symbol, {})
        last_p = sec_d.get('last_price')
        return {
            "cmp": safe_num(last_p),
            "market_cap_cr": None,
            "forward_eps_1y": None,
            "forward_pe": None,
            "ttm_pe": None,
            "historical_median_pe": hist_med_pe,
            "target_price": {
                "low": None,
                "median": None,
                "mean": None,
                "high": None,
                "implied_upside_pct": None
            }
        }

    cmp_val = safe_num(raw.get('cmp'))
    mcap_val = raw.get('market_cap')
    mcap_cr = safe_num(float(mcap_val) / 1e7) if mcap_val is not None and not pd.isna(mcap_val) else None
    fwd_eps = safe_num(raw.get('forward_eps'))
    fwd_pe = safe_num(raw.get('forward_pe'))
    ttm_pe = safe_num(raw.get('trailing_pe'))

    t_low = safe_num(raw.get('target_low'))
    t_median = safe_num(raw.get('target_median'))
    t_mean = safe_num(raw.get('target_mean'))
    t_high = safe_num(raw.get('target_high'))

    upside = safe_num(raw.get('upside_pct'))
    if upside is None and cmp_val and t_mean and cmp_val > 0:
        upside = safe_num(((t_mean / cmp_val) - 1.0) * 100.0)

    return {
        "cmp": cmp_val,
        "market_cap_cr": mcap_cr,
        "forward_eps_1y": fwd_eps,
        "forward_pe": fwd_pe,
        "ttm_pe": ttm_pe,
        "historical_median_pe": hist_med_pe,
        "target_price": {
            "low": t_low,
            "median": t_median,
            "mean": t_mean,
            "high": t_high,
            "implied_upside_pct": upside
        }
    }


def extract_cycle_performance(risk_metric_df, has_sec=False, sname_mkt="Benchmark", sname_stk="Stock1", sname_stk2=None):
    """Maps computed risk_metrics table into cycle_performance list with solo mode secondary=null."""
    if risk_metric_df is None or risk_metric_df.empty:
        return []

    cycles_list = []
    for _, row in risk_metric_df.iterrows():
        phase_str = str(row.get('Phase', ''))
        if not phase_str or phase_str.lower() in ['nan', 'none']:
            continue

        sd = row.get('Start Date')
        ed = row.get('End Date')
        sd_str = sd.strftime("%Y-%m-%d") if hasattr(sd, 'strftime') else (str(sd) if pd.notna(sd) else None)
        ed_str = ed.strftime("%Y-%m-%d") if hasattr(ed, 'strftime') else (str(ed) if pd.notna(ed) else None)

        mkt_ret = None
        for cand in [f"{sname_mkt} Return", "Benchmark Return", "Market Return"]:
            if cand in row and pd.notna(row[cand]):
                mkt_ret = safe_num(row[cand])
                break
        if mkt_ret is None:
            for c in row.index:
                if "return" in str(c).lower() and sname_stk.lower() not in str(c).lower() and (not sname_stk2 or sname_stk2.lower() not in str(c).lower()):
                    mkt_ret = safe_num(row[c])
                    break

        stk_ret = None
        for cand in [f"{sname_stk} Return", "Stock Return", "Primary Return"]:
            if cand in row and pd.notna(row[cand]):
                stk_ret = safe_num(row[cand])
                break
        if stk_ret is None:
            for c in row.index:
                if "return" in str(c).lower() and sname_stk.lower() in str(c).lower():
                    stk_ret = safe_num(row[c])
                    break

        stk_beta = None
        for cand in [f"{sname_stk} Beta", "beta", "Beta", "Primary Beta"]:
            if cand in row and pd.notna(row[cand]):
                stk_beta = safe_num(row[cand])
                break

        stk2_ret = None
        stk2_beta = None
        if has_sec and sname_stk2:
            for cand in [f"{sname_stk2} Return", "Secondary Return"]:
                if cand in row and pd.notna(row[cand]):
                    stk2_ret = safe_num(row[cand])
                    break
            for cand in [f"{sname_stk2} Beta", "Secondary Beta"]:
                if cand in row and pd.notna(row[cand]):
                    stk2_beta = safe_num(row[cand])
                    break

        cycles_list.append({
            "phase": phase_str,
            "start_date": sd_str,
            "end_date": ed_str,
            "benchmark_return_pct": mkt_ret,
            "primary_return_pct": stk_ret,
            "primary_beta": stk_beta,
            "secondary_return_pct": stk2_ret,
            "secondary_beta": stk2_beta
        })

    return cycles_list


def extract_relative_value_summary(norm_prices_df, eps_df1, eps_df2=None, has_dual=False, sdate=None, edate=None):
    """
    Computes horizon-aligned relative value and EPS growth metrics.
    In Solo Mode (has_dual=False), secondary and pair fields are set strictly to None/null.
    """
    summary = {
        "primary_vs_benchmark_relval_base100": None,
        "secondary_vs_benchmark_relval_base100": None,
        "pair_price_ratio_relval_base100": None,
        "pair_price_multiplier": None,
        "pair_eps_multiple_relval": None,
        "primary_total_eps_growth_pct": None,
        "secondary_total_eps_growth_pct": None
    }

    # 1. Price Relative Value series
    if norm_prices_df is not None and not norm_prices_df.empty and len(norm_prices_df.columns) >= 2:
        mkt_c = norm_prices_df.columns[0]
        stk1_c = norm_prices_df.columns[1]
        stk2_c = norm_prices_df.columns[2] if (len(norm_prices_df.columns) >= 3 and norm_prices_df.columns[2] != 'Phase') else None

        s1 = norm_prices_df[stk1_c].dropna()
        mkt = norm_prices_df[mkt_c].dropna()
        c_idx1 = s1.index.intersection(mkt.index)
        if not c_idx1.empty:
            rv1 = (s1.loc[c_idx1] / mkt.loc[c_idx1].replace(0, np.nan)) * 100.0
            rv1_clean = rv1.dropna()
            if not rv1_clean.empty:
                summary["primary_vs_benchmark_relval_base100"] = safe_num(rv1_clean.iloc[-1])

        if has_dual and stk2_c and stk2_c in norm_prices_df.columns:
            s2 = norm_prices_df[stk2_c].dropna()
            c_idx2 = s2.index.intersection(mkt.index)
            if not c_idx2.empty:
                rv2 = (s2.loc[c_idx2] / mkt.loc[c_idx2].replace(0, np.nan)) * 100.0
                rv2_clean = rv2.dropna()
                if not rv2_clean.empty:
                    summary["secondary_vs_benchmark_relval_base100"] = safe_num(rv2_clean.iloc[-1])

            c_idx_p = s1.index.intersection(s2.index)
            if not c_idx_p.empty:
                rv_p = (s1.loc[c_idx_p] / s2.loc[c_idx_p].replace(0, np.nan)) * 100.0
                rv_p_clean = rv_p.dropna()
                if not rv_p_clean.empty:
                    val_base100 = safe_num(rv_p_clean.iloc[-1])
                    summary["pair_price_ratio_relval_base100"] = val_base100
                    if val_base100 is not None:
                        summary["pair_price_multiplier"] = safe_num(val_base100 / 100.0)

    # 2. Total EPS Growth & EPS Multiple (Horizon-Aligned to sdate & edate)
    q1 = _prepare_ttm_df(eps_df1, s_date=sdate, e_date=edate)
    mult1 = None
    if not q1.empty:
        b_ttm1 = float(q1['TTM EPS'].iloc[0])
        l_ttm1 = float(q1['TTM EPS'].iloc[-1])
        if b_ttm1 > 0:
            summary["primary_total_eps_growth_pct"] = safe_num(((l_ttm1 / b_ttm1) - 1.0) * 100.0)
            mult1 = l_ttm1 / b_ttm1

    mult2 = None
    if has_dual and eps_df2 is not None:
        q2 = _prepare_ttm_df(eps_df2, s_date=sdate, e_date=edate)
        if not q2.empty:
            b_ttm2 = float(q2['TTM EPS'].iloc[0])
            l_ttm2 = float(q2['TTM EPS'].iloc[-1])
            if b_ttm2 > 0:
                summary["secondary_total_eps_growth_pct"] = safe_num(((l_ttm2 / b_ttm2) - 1.0) * 100.0)
                mult2 = l_ttm2 / b_ttm2

    if has_dual and mult1 is not None and mult2 is not None and mult2 > 0:
        summary["pair_eps_multiple_relval"] = safe_num(mult1 / mult2)

    return summary


def extract_eps_trajectory_data(eps_df, price_series=None, sdate=None, edate=None):
    """
    Builds EPS trajectory metrics:
    - CAGRs: calculated stepping back 4, 12, 20, 40 quarters from latest quarter.
    - quarterly_ttm_eps & median_yoy_growth_pct: trimmed to analysis_horizon.
    """
    if eps_df is None or eps_df.empty or 'TTM EPS' not in eps_df.columns:
        return None

    clean_df = eps_df.dropna(subset=['TTM EPS']).sort_values('Date', ascending=True).copy()
    if clean_df.empty:
        return None

    # Slice quarters to analysis_horizon
    vis_df = clean_df.copy()
    if sdate:
        try:
            s_dt = pd.to_datetime(sdate).normalize()
            f_s = vis_df[vis_df['Date'] >= s_dt]
            if not f_s.empty:
                vis_df = f_s
        except Exception:
            pass
    if edate:
        try:
            e_dt = pd.to_datetime(edate).normalize()
            f_e = vis_df[vis_df['Date'] <= e_dt]
            if not f_e.empty:
                vis_df = f_e
        except Exception:
            pass

    # Median YoY growth within the active analysis horizon
    med_g = safe_num(vis_df['YoY Growth'].median()) if 'YoY Growth' in vis_df.columns and not vis_df.empty else None

    # CAGRs computed from full clean history relative to latest record in horizon
    latest_rec = vis_df.iloc[-1]
    latest_dt = latest_rec['Date']
    latest_ttm = float(latest_rec['TTM EPS'])

    # Find position of latest_dt in clean_df
    matches = clean_df[clean_df['Date'] == latest_dt].index
    idx_latest = clean_df.index.get_loc(matches[0]) if len(matches) > 0 else len(clean_df) - 1

    def _cagr(n_qtrs, n_yrs):
        idx_base = idx_latest - n_qtrs
        if idx_base >= 0 and latest_ttm > 0:
            base_rec = clean_df.iloc[idx_base]
            base_ttm = float(base_rec['TTM EPS'])
            if base_ttm > 0:
                return safe_num(((latest_ttm / base_ttm) ** (1.0 / n_yrs) - 1.0) * 100.0)
        return None

    cagr_1y = _cagr(4, 1)
    cagr_3y = _cagr(12, 3)
    cagr_5y = _cagr(20, 5)
    cagr_10y = _cagr(40, 10)

    # Price lookup series
    stk_lookup = price_series.copy() if price_series is not None and not price_series.empty else pd.Series(dtype=float)
    if not stk_lookup.empty:
        stk_lookup.index = pd.to_datetime(stk_lookup.index).normalize()
        try:
            stk_lookup.index = stk_lookup.index.tz_localize(None)
        except Exception:
            pass

    # Build quarterly_ttm_eps strictly trimmed to analysis_horizon (latest first)
    q_list = []
    for _, row in vis_df.iloc[::-1].iterrows():
        dt_val = row['Date']
        qtr_str = str(row.get('Quarter', ''))
        ttm_val = safe_num(row.get('TTM EPS'))
        yoy_g = safe_num(row.get('YoY Growth'))

        p_val = None
        if not stk_lookup.empty:
            asof_p = stk_lookup.asof(pd.to_datetime(dt_val).normalize())
            if pd.notna(asof_p):
                p_val = float(asof_p)

        tr_pe = None
        if p_val is not None and ttm_val is not None and ttm_val > 0:
            tr_pe = safe_num(p_val / ttm_val)

        peg = None
        if tr_pe is not None and yoy_g is not None and yoy_g > 0:
            peg = safe_num(tr_pe / yoy_g)

        q_list.append({
            "quarter": qtr_str,
            "ttm_eps": ttm_val,
            "yoy_growth_pct": yoy_g,
            "trailing_pe": tr_pe,
            "ttm_peg": peg
        })

    return {
        "median_yoy_growth_pct": med_g,
        "cagr_1y_pct": cagr_1y,
        "cagr_3y_pct": cagr_3y,
        "cagr_5y_pct": cagr_5y,
        "cagr_10y_pct": cagr_10y,
        "quarterly_ttm_eps": q_list
    }


def get_usdinr_exchange_rate():
    """
    Fetches the latest USDINR=X exchange rate from yfinance,
    falling back to 84.0 on network errors or missing data.
    """
    rate = None
    try:
        import yfinance as yf
        fx = yf.Ticker("USDINR=X")
        if hasattr(fx, "fast_info") and fx.fast_info:
            rate = fx.fast_info.get("lastPrice") or fx.fast_info.get("last_price")
        if rate is None and hasattr(fx, "info") and fx.info:
            rate = fx.info.get("regularMarketPrice") or fx.info.get("currentPrice")
        if rate is not None:
            r_float = float(rate)
            if r_float > 0 and not math.isnan(r_float) and not math.isinf(r_float):
                return round(r_float, 2)
    except Exception as e:
        print(f"Note: USDINR=X fetch note ({e}), using fallback 84.0")
    return 84.0


def extract_annual_financials_4y(ticker_symbol):
    """Extracts 4-year annual financials and computes EBITDA and PAT margins."""
    if not ticker_symbol or str(ticker_symbol).strip().upper() in ["NA", "NONE", "", "NULL"]:
        return None

    raw_inc_ann = None
    stmt_cache = getattr(sc, '_LAST_SECURITY_STATEMENTS', {}).get(ticker_symbol, {})
    if stmt_cache:
        raw_inc_ann = stmt_cache.get('raw_inc_ann')

    if raw_inc_ann is None or raw_inc_ann.empty:
        raw_sym = str(ticker_symbol).replace(".NS", "").replace(".BO", "")
        for k, v in getattr(sc, '_LAST_SECURITY_STATEMENTS', {}).items():
            if str(k).replace(".NS", "").replace(".BO", "") == raw_sym:
                raw_inc_ann = v.get('raw_inc_ann')
                stmt_cache = v
                break

    if raw_inc_ann is None or raw_inc_ann.empty:
        return None

    # Currency Normalization Check:
    # If financialCurrency is "USD" and trading currency is "INR" (e.g. INFY.NS ADRs),
    # convert monetary figures to INR (Cr) using USDINR=X rate (fallback 84.0).
    # Margin percentages and basic_avg_shares_cr are left untouched.
    fin_curr = None
    trading_curr = "INR" if (str(ticker_symbol).upper().endswith(".NS") or str(ticker_symbol).upper().endswith(".BO")) else "INR"

    if stmt_cache and 'financial_currency' in stmt_cache:
        fin_curr = stmt_cache.get('financial_currency')

    if not fin_curr:
        try:
            import yfinance as yf
            t = yf.Ticker(ticker_symbol)
            if hasattr(t, "info") and t.info:
                fin_curr = t.info.get("financialCurrency")
                tc = t.info.get("currency")
                if tc:
                    trading_curr = str(tc).upper()
        except Exception:
            pass

    fin_curr_str = str(fin_curr).strip().upper() if fin_curr else ""
    is_usd_fin = (fin_curr_str == "USD" and trading_curr == "INR")
    fx_rate = get_usdinr_exchange_rate() if is_usd_fin else 1.0

    recent_cols = sorted(raw_inc_ann.columns, reverse=True)[:4]

    def _find_val(df, candidates, col):
        for c in candidates:
            if c in df.index and col in df.columns:
                val = df.loc[c, col]
                if pd.notna(val):
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        pass
        return None

    financials_list = []
    for col in recent_cols:
        ts = pd.to_datetime(col)
        fy_str = f"FY {ts.year}"

        # 1. Total Revenue
        rev_raw = _find_val(raw_inc_ann, ["Total Revenue", "Operating Revenue"], col)
        rev_cr = safe_num(rev_raw / 1e7) if rev_raw is not None else None

        # 2. Cost of Revenue & Gross Profit
        gp_raw = _find_val(raw_inc_ann, ["Gross Profit"], col)
        if gp_raw is None and rev_raw is not None:
            cor_raw = _find_val(raw_inc_ann, ["Cost Of Revenue", "Reconciled Cost Of Revenue"], col)
            if cor_raw is not None:
                gp_raw = rev_raw - cor_raw
        gp_cr = safe_num(gp_raw / 1e7) if gp_raw is not None else None

        # 3. EBITDA
        ebitda_raw = _find_val(raw_inc_ann, ["EBITDA", "Normalized EBITDA"], col)
        if ebitda_raw is None:
            op_inc = _find_val(raw_inc_ann, ["Operating Income", "EBIT"], col)
            dep = _find_val(raw_inc_ann, ["Reconciled Depreciation", "Depreciation Amortization Depletion", "Depreciation And Amortization"], col)
            if op_inc is not None and dep is not None:
                ebitda_raw = op_inc + dep
            elif op_inc is not None:
                ebitda_raw = op_inc
        ebitda_cr = safe_num(ebitda_raw / 1e7) if ebitda_raw is not None else None

        # 4. EBIT / Operating Profit
        ebit_raw = _find_val(raw_inc_ann, ["EBIT", "Operating Income"], col)
        ebit_cr = safe_num(ebit_raw / 1e7) if ebit_raw is not None else None

        # 5. Net Income
        net_inc_raw = _find_val(raw_inc_ann, ["Net Income Common Stockholders", "Net Income Continuous Operations", "Net Income From Continuing Operation Net Minority Interest"], col)
        net_inc_cr = safe_num(net_inc_raw / 1e7) if net_inc_raw is not None else None

        # 6. Margins (%) - computed on unscaled ratios or identically scaled ratios
        ebitda_margin = None
        if ebitda_cr is not None and rev_cr is not None and rev_cr > 0:
            ebitda_margin = safe_num((ebitda_cr / rev_cr) * 100.0)

        pat_margin = None
        if net_inc_cr is not None and rev_cr is not None and rev_cr > 0:
            pat_margin = safe_num((net_inc_cr / rev_cr) * 100.0)

        # 7. Basic EPS & Share counts
        b_eps = _find_val(raw_inc_ann, ["Basic EPS", "Diluted EPS"], col)
        basic_eps = safe_num(b_eps) if b_eps is not None else None

        shares_raw = _find_val(raw_inc_ann, ["Basic Average Shares", "Diluted Average Shares", "Ordinary Shares Number"], col)
        basic_avg_shares_cr = safe_num(shares_raw / 1e7) if shares_raw is not None else None

        # Apply FX Normalization to monetary figures if financialCurrency == "USD" and trading in INR
        rev_cr_norm = safe_num(rev_cr * fx_rate) if rev_cr is not None else None
        gp_cr_norm = safe_num(gp_cr * fx_rate) if gp_cr is not None else None
        ebitda_cr_norm = safe_num(ebitda_cr * fx_rate) if ebitda_cr is not None else None
        ebit_cr_norm = safe_num(ebit_cr * fx_rate) if ebit_cr is not None else None
        net_inc_cr_norm = safe_num(net_inc_cr * fx_rate) if net_inc_cr is not None else None
        basic_eps_norm = safe_num(basic_eps * fx_rate) if basic_eps is not None else None

        financials_list.append({
            "fiscal_year": fy_str,
            "total_revenue_cr": rev_cr_norm,
            "gross_profit_cr": gp_cr_norm,
            "ebitda_cr": ebitda_cr_norm,
            "ebit_cr": ebit_cr_norm,
            "net_income_cr": net_inc_cr_norm,
            "ebitda_margin_pct": ebitda_margin,
            "pat_margin_pct": pat_margin,
            "basic_eps": basic_eps_norm,
            "basic_avg_shares_cr": basic_avg_shares_cr
        })

    return financials_list

    return financials_list


def build_ai_analysis_payload(benchmark, primary_ticker, primary_name, secondary_ticker=None, secondary_name=None, sdate=None, edate=None, cycle_type="bull_bear"):
    """
    Assembles the complete AI Analysis JSON payload complying with schema_version: "1.0".
    Reuses 100% of pre-computed report data in memory (zero extra fetches).
    Supports Pair Mode and Solo Mode.
    """
    has_secondary = bool(secondary_ticker and str(secondary_ticker).strip().upper() not in ["", "NA", "NONE", "NULL"])
    analysis_mode = "pair" if has_secondary else "solo"
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    rep_data = getattr(sc, '_LAST_REPORT_DATA', {})
    norm_prices_df = rep_data.get('norm_prices_df')
    prices_df = rep_data.get('prices_df')
    risk_metric_df = rep_data.get('risk_metric_df')
    eps_df1 = rep_data.get('eps_df')
    eps_df2 = rep_data.get('eps_df2')
    act_sdate = rep_data.get('act_sdate') or sdate
    act_edate = rep_data.get('act_edate') or edate

    sdate_str = act_sdate.strftime("%Y-%m-%d") if hasattr(act_sdate, 'strftime') else (str(act_sdate) if act_sdate else None)
    edate_str = act_edate.strftime("%Y-%m-%d") if hasattr(act_edate, 'strftime') else (str(act_edate) if act_edate else None)

    # 1. Metadata
    metadata = {
        "analysis_mode": analysis_mode,
        "currency": "INR",
        "benchmark": benchmark or "^NSEI",
        "primary_security": {
            "ticker": primary_ticker,
            "name": primary_name or sc.short_name(primary_ticker)
        },
        "secondary_security": {
            "ticker": secondary_ticker,
            "name": secondary_name or sc.short_name(secondary_ticker)
        } if has_secondary else None,
        "analysis_horizon": {
            "start_date": sdate_str,
            "end_date": edate_str
        }
    }

    # 2. Valuation Snapshot
    pe_data1 = rep_data.get('pe_data')
    pe_data2 = rep_data.get('pe_data2')
    val_primary = extract_valuation_snapshot(primary_ticker, pe_data=pe_data1)
    val_secondary = extract_valuation_snapshot(secondary_ticker, pe_data=pe_data2) if has_secondary else None
    valuation_snapshot = {
        "primary": val_primary,
        "secondary": val_secondary
    }

    # 3. Cycle Performance
    sname_mkt = sc.short_name(benchmark or "^NSEI")
    sname_stk = sc.short_name(primary_ticker)
    sname_stk2 = sc.short_name(secondary_ticker) if has_secondary else None
    cycle_perf = extract_cycle_performance(
        risk_metric_df,
        has_sec=has_secondary,
        sname_mkt=sname_mkt,
        sname_stk=sname_stk,
        sname_stk2=sname_stk2
    )

    # 4. Relative Value Summary (Horizon-Aligned)
    rv_summary = extract_relative_value_summary(
        norm_prices_df,
        eps_df1,
        eps_df2=eps_df2,
        has_dual=has_secondary,
        sdate=act_sdate,
        edate=act_edate
    )

    # 5. EPS Trajectory (Horizon-Aligned & Trimmed)
    p1_series = prices_df[prices_df.columns[1]] if (prices_df is not None and len(prices_df.columns) >= 2) else None
    p2_series = prices_df[prices_df.columns[2]] if (has_secondary and prices_df is not None and len(prices_df.columns) >= 3 and prices_df.columns[2] != 'Phase') else None

    eps_primary = extract_eps_trajectory_data(eps_df1, price_series=p1_series, sdate=act_sdate, edate=act_edate)
    eps_secondary = extract_eps_trajectory_data(eps_df2, price_series=p2_series, sdate=act_sdate, edate=act_edate) if has_secondary else None
    eps_trajectory = {
        "primary": eps_primary,
        "secondary": eps_secondary
    }

    # 6. Annual Financials 4Y
    fin_primary = extract_annual_financials_4y(primary_ticker)
    fin_secondary = extract_annual_financials_4y(secondary_ticker) if has_secondary else None
    annual_financials = {
        "primary": fin_primary or [],
        "secondary": fin_secondary
    }

    # 7. Relative Volatility & Volume-Confirmed Idiosyncratic Shocks
    from . import ia_volatility
    vol_analysis = rep_data.get('vol_analysis')
    if not vol_analysis:
        volume_df = rep_data.get('volume_df')
        ben_sym = benchmark or rep_data.get('benchmark') or "^NSEI"
        vol_analysis = ia_volatility.build_relative_volatility_analysis(
            prices_df=prices_df,
            volume_df=volume_df,
            benchmark=ben_sym,
            primary_ticker=primary_ticker,
            secondary_ticker=secondary_ticker,
            primary_name=primary_name or sc.short_name(primary_ticker),
            secondary_name=secondary_name or (sc.short_name(secondary_ticker) if has_secondary else None),
            benchmark_name=sc.short_name(ben_sym)
        )
    vol_shocks_summary = ia_volatility.extract_volatility_and_shocks_summary(vol_analysis)

    # 8. Date-Anchored Event Signals (Abnormal Return Shocks, Share Count Dynamics, Regimes)
    from . import ia_event_signals
    volume_df = rep_data.get('volume_df')
    ben_sym = benchmark or rep_data.get('benchmark') or "^NSEI"
    event_signals_block = ia_event_signals.build_event_signals_block(
        prices_df=prices_df,
        volume_df=volume_df,
        benchmark=ben_sym,
        primary_ticker=primary_ticker,
        secondary_ticker=secondary_ticker,
        fin_primary=fin_primary,
        fin_secondary=fin_secondary,
        has_secondary=has_secondary
    )

    payload = {
        "schema_version": "1.0",
        "generated_at": now_iso,
        "metadata": metadata,
        "valuation_snapshot": valuation_snapshot,
        "cycle_performance": cycle_perf,
        "relative_value_summary": rv_summary,
        "eps_trajectory": eps_trajectory,
        "annual_financials_4y": annual_financials,
        "volatility_and_shocks": vol_shocks_summary,
        "event_signals": event_signals_block
    }

    return clean_for_json(payload)
