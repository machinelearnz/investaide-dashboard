# -*- encoding: utf-8 -*-
"""
InvestAide Relative Volatility & Idiosyncratic Shock Detector Module
Calculates 20-Day rolling annualized volatility (5D SMA smoothed),
relative volatility ratios vs benchmark, 20-Day relative volume multiples,
and detects volume-confirmed idiosyncratic shock catalysts for Primary & Secondary securities.
"""

import math
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


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


def compute_security_volatility(price_series, benchmark_price_series, volume_series=None):
    """
    Computes 20-day rolling annualized volatility (5D SMA smoothed),
    relative volatility ratio vs benchmark, and relative volume multiple.
    """
    if price_series is None or price_series.empty or benchmark_price_series is None or benchmark_price_series.empty:
        return {}

    # Common valid index alignment
    common_idx = price_series.dropna().index.intersection(benchmark_price_series.dropna().index)
    if len(common_idx) < 25:
        return {}

    p_stock = price_series.loc[common_idx].astype(float)
    p_bench = benchmark_price_series.loc[common_idx].astype(float)

    # 1. Log returns
    r_stock = np.log(p_stock / p_stock.shift(1))
    r_bench = np.log(p_bench / p_bench.shift(1))

    # 2. 20-day rolling annualized volatility: std(r_20d) * sqrt(252) * 100
    vol_20d_stock = r_stock.rolling(window=20, min_periods=10).std(ddof=1) * np.sqrt(252) * 100.0
    vol_20d_bench = r_bench.rolling(window=20, min_periods=10).std(ddof=1) * np.sqrt(252) * 100.0

    # 5-day SMA smoothing
    vol_20d_sma5_stock = vol_20d_stock.rolling(window=5, min_periods=1).mean()
    vol_20d_sma5_bench = vol_20d_bench.rolling(window=5, min_periods=1).mean()

    # 3. Relative Volatility Ratio
    rel_vol_ratio = (vol_20d_sma5_stock / vol_20d_sma5_bench).replace([np.inf, -np.inf], np.nan)
    valid_ratios = rel_vol_ratio.dropna()

    median_vol_ratio = float(valid_ratios.median()) if not valid_ratios.empty else 1.0
    current_vol_ratio = float(valid_ratios.iloc[-1]) if not valid_ratios.empty else None
    p95_vol_ratio = float(valid_ratios.quantile(0.95)) if not valid_ratios.empty else 2.0

    current_vol_pct = float(vol_20d_sma5_stock.dropna().iloc[-1]) if not vol_20d_sma5_stock.dropna().empty else None
    median_vol_pct = float(vol_20d_sma5_stock.dropna().median()) if not vol_20d_sma5_stock.dropna().empty else None
    benchmark_median_vol_pct = float(vol_20d_sma5_bench.dropna().median()) if not vol_20d_sma5_bench.dropna().empty else None

    # 4. Relative Volume Multiple
    if volume_series is not None and not volume_series.empty:
        v_stock = volume_series.reindex(common_idx).fillna(0).astype(float)
        mean_v20 = v_stock.rolling(window=20, min_periods=5).mean().replace(0, np.nan)
        rel_volume = (v_stock / mean_v20).replace([np.inf, -np.inf], np.nan).fillna(1.0)
    else:
        v_stock = pd.Series(0, index=common_idx)
        rel_volume = pd.Series(1.0, index=common_idx)

    return {
        'common_idx': common_idx,
        'price': p_stock,
        'bench_price': p_bench,
        'volume': v_stock,
        'vol_20d_sma5': vol_20d_sma5_stock,
        'bench_vol_20d_sma5': vol_20d_sma5_bench,
        'rel_vol_ratio': rel_vol_ratio,
        'rel_volume': rel_volume,
        'median_vol_ratio': median_vol_ratio,
        'current_vol_ratio': current_vol_ratio,
        'p95_vol_ratio': p95_vol_ratio,
        'current_vol_pct': current_vol_pct,
        'median_vol_pct': median_vol_pct,
        'benchmark_median_vol_pct': benchmark_median_vol_pct
    }


def detect_idiosyncratic_shocks(metrics_dict):
    """
    Detects volume-confirmed idiosyncratic shock events:
    Trigger 1: rel_vol_ratio >= max(p95_vol_ratio, 1.8 * median_vol_ratio) AND peak rel_volume >= 2.5 in +/- 5 trading-day window.
    Trigger 2: peak rel_volume >= 4.0 in window with normal volatility ("quiet_volume_surge").
    Clusters adjacent days within 30 calendar days around peak severity, and retains Top 3 events.
    """
    if not metrics_dict:
        return []

    common_idx = metrics_dict['common_idx']
    p_stock = metrics_dict['price']
    rel_vol_ratio = metrics_dict['rel_vol_ratio']
    rel_volume = metrics_dict['rel_volume']
    median_vol_ratio = metrics_dict['median_vol_ratio']
    p95_vol_ratio = metrics_dict['p95_vol_ratio']

    spike_threshold = max(p95_vol_ratio, 1.8 * median_vol_ratio)
    n = len(common_idx)
    candidates = []

    for i in range(n):
        rv = rel_vol_ratio.iloc[i]
        if pd.isna(rv):
            continue

        w_start = max(0, i - 5)
        w_end = min(n, i + 6)
        window_vm = rel_volume.iloc[w_start:w_end]
        peak_vm = float(window_vm.max()) if not window_vm.dropna().empty else 1.0

        is_vol_spike = (rv >= spike_threshold) and (peak_vm >= 2.5)

        if is_vol_spike:
            stype = "volume_confirmed_vol_spike"
            severity = float(rv) * peak_vm
            dt = common_idx[i]

            # 10-day window price return (+/- 5 trading days)
            p_start = float(p_stock.iloc[w_start])
            p_end = float(p_stock.iloc[min(n - 1, i + 5)])
            w_ret = round(((p_end - p_start) / p_start) * 100.0, 2) if p_start > 0 else 0.0

            candidates.append({
                'idx': i,
                'date': dt,
                'date_str': dt.strftime('%Y-%m-%d'),
                'month': dt.strftime('%Y-%m'),
                'vol_vs_benchmark_ratio': round(float(rv), 2),
                'median_vol_ratio': round(float(median_vol_ratio), 2),
                'volume_multiple': round(float(peak_vm), 2),
                'window_return_pct': w_ret,
                'shock_type': stype,
                'severity': severity
            })

    if not candidates:
        return []

    # De-duplication: Iterative peak clustering within 30 calendar days
    candidates_pool = candidates.copy()
    clustered_events = []

    while candidates_pool:
        # Pick candidate with global peak severity
        best = max(candidates_pool, key=lambda x: x['severity'])
        clustered_events.append(best)
        # Suppress all candidates within 30 calendar days of this peak
        peak_date = best['date']
        candidates_pool = [c for c in candidates_pool if abs((c['date'] - peak_date).days) > 30]

    # Rank by severity descending, retain Top 3
    clustered_events.sort(key=lambda x: x['severity'], reverse=True)
    top3 = clustered_events[:3]

    # Sort chronologically for clean presentation
    top3.sort(key=lambda x: x['date'])
    return top3


def build_relative_volatility_analysis(prices_df, volume_df, benchmark, primary_ticker, secondary_ticker=None,
                                       primary_name=None, secondary_name=None, benchmark_name=None):
    """
    Orchestrates relative volatility analysis for primary and optional secondary securities.
    Returns calculated metrics and detected idiosyncratic shocks.
    """
    if prices_df is None or prices_df.empty or len(prices_df.columns) < 2:
        return None

    # Benchmark column
    b_col = benchmark if benchmark in prices_df.columns else prices_df.columns[0]
    p1_col = primary_ticker if primary_ticker in prices_df.columns else prices_df.columns[1]

    # Primary volume series
    v1_series = None
    if volume_df is not None and not volume_df.empty:
        if primary_ticker in volume_df.columns:
            v1_series = volume_df[primary_ticker]
        elif len(volume_df.columns) >= 2:
            v1_series = volume_df[volume_df.columns[1]]

    prim_metrics = compute_security_volatility(prices_df[p1_col], prices_df[b_col], volume_series=v1_series)
    prim_shocks = detect_idiosyncratic_shocks(prim_metrics) if prim_metrics else []

    # Secondary analysis
    has_secondary = bool(secondary_ticker and str(secondary_ticker).strip().upper() not in ["", "NA", "NONE", "NULL"])
    sec_metrics = None
    sec_shocks = []

    if has_secondary and len(prices_df.columns) >= 3 and prices_df.columns[2] != 'Phase':
        p2_col = secondary_ticker if secondary_ticker in prices_df.columns else prices_df.columns[2]
        v2_series = None
        if volume_df is not None and not volume_df.empty:
            if secondary_ticker in volume_df.columns:
                v2_series = volume_df[secondary_ticker]
            elif len(volume_df.columns) >= 3:
                v2_series = volume_df[volume_df.columns[2]]

        sec_metrics = compute_security_volatility(prices_df[p2_col], prices_df[b_col], volume_series=v2_series)
        sec_shocks = detect_idiosyncratic_shocks(sec_metrics) if sec_metrics else []

    return {
        'benchmark': benchmark or "^NSEI",
        'benchmark_name': benchmark_name or "Benchmark",
        'primary_ticker': primary_ticker,
        'primary_name': primary_name or primary_ticker,
        'secondary_ticker': secondary_ticker if has_secondary else None,
        'secondary_name': secondary_name if has_secondary else None,
        'has_secondary': has_secondary,
        'primary_metrics': prim_metrics,
        'primary_shocks': prim_shocks,
        'secondary_metrics': sec_metrics,
        'secondary_shocks': sec_shocks,
        'benchmark_median_vol_pct': prim_metrics.get('benchmark_median_vol_pct') if prim_metrics else None
    }


def build_volatility_shocks_plotly_chart(vol_analysis):
    """
    Renders an interactive dark-mode 3-row vertically stacked Plotly chart matching InvestAide design specifications:
    Row 1 (Top): Relative Volatility Ratio (Stock/Benchmark) with median embedded in legend & shock diamond markers.
    Row 2 (Middle): Raw 5D-smoothed 20D Annualized Volatility (%) for Primary, Secondary (if pair), and Benchmark.
    Row 3 (Bottom): Rel. Volume (x 20D Avg) bar chart (filtered to >= 2.0x surges, overlay mode).
    """
    if not vol_analysis or not vol_analysis.get('primary_metrics'):
        return "<div><h5 style='text-align:center; color:#94A3B8; padding:20px;'>No volatility data available.</h5></div>"

    m1 = vol_analysis['primary_metrics']
    m2 = vol_analysis['secondary_metrics']
    has_sec = vol_analysis['has_secondary'] and (m2 is not None)

    p1_name = vol_analysis.get('primary_name') or vol_analysis.get('primary_ticker') or "Primary"
    p2_name = vol_analysis.get('secondary_name') or vol_analysis.get('secondary_ticker') or "Secondary"
    b_name = vol_analysis.get('benchmark_name') or "Benchmark"

    # High-Contrast Color Palette (Dark Mode)
    c_primary = "#38BDF8"       # Electric Cyan
    c_secondary = "#F59E0B"     # Warm Gold / Amber
    c_bench = "#94A3B8"         # Subtle dashed Slate
    c_shock_p = "#F43F5E"       # Rose diamond for Primary
    c_shock_s = "#F59E0B"       # Amber diamond for Secondary

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.46, 0.34, 0.20]
    )

    # -------------------------------------------------------------
    # ROW 1: Relative Volatility Ratio vs Benchmark
    # -------------------------------------------------------------
    med1 = m1['median_vol_ratio']
    fig.add_trace(go.Scatter(
        x=m1['rel_vol_ratio'].index,
        y=m1['rel_vol_ratio'],
        name=f"{p1_name} / {b_name} Vol Ratio (Med: {med1:.2f}x)",
        mode="lines",
        line=dict(color=c_primary, width=2.2),
        hovertemplate=f"<b>{p1_name} Rel Vol:</b> %{{y:.2f}}x<extra></extra>"
    ), row=1, col=1)

    # Primary Median Line (No colliding text annotations)
    fig.add_hline(
        y=med1,
        line=dict(color=c_primary, width=1.2, dash="dash"),
        row=1, col=1
    )

    # Secondary Ratio Trace (if pair mode)
    if has_sec and m2:
        med2 = m2['median_vol_ratio']
        fig.add_trace(go.Scatter(
            x=m2['rel_vol_ratio'].index,
            y=m2['rel_vol_ratio'],
            name=f"{p2_name} / {b_name} Vol Ratio (Med: {med2:.2f}x)",
            mode="lines",
            line=dict(color=c_secondary, width=2.0),
            hovertemplate=f"<b>{p2_name} Rel Vol:</b> %{{y:.2f}}x<extra></extra>"
        ), row=1, col=1)

        # Secondary Median Line (No colliding text annotations)
        fig.add_hline(
            y=med2,
            line=dict(color=c_secondary, width=1.2, dash="dash"),
            row=1, col=1
        )

    # Benchmark Parity Line (1.0x)
    fig.add_hline(
        y=1.0,
        line=dict(color="rgba(148, 163, 184, 0.35)", width=1.0, dash="dot"),
        row=1, col=1
    )

    # Highlighted Shock Markers (Primary) - Rose diamond with white border
    shocks1 = vol_analysis.get('primary_shocks', [])
    if shocks1:
        x_s1 = [s['date'] for s in shocks1]
        y_s1 = [s['vol_vs_benchmark_ratio'] for s in shocks1]
        customdata1 = [[
            s['date_str'],
            s['vol_vs_benchmark_ratio'],
            s['volume_multiple'],
            s['window_return_pct'],
            "Volume-Confirmed Vol Spike"
        ] for s in shocks1]

        fig.add_trace(go.Scatter(
            x=x_s1,
            y=y_s1,
            name=f"{p1_name} Shocks ({len(shocks1)})",
            mode="markers",
            marker=dict(
                symbol="diamond",
                size=12,
                color=c_shock_p,
                line=dict(width=2, color="#FFFFFF")
            ),
            customdata=customdata1,
            hovertemplate=(
                f"<b>⚡ {p1_name} Volatility Shock</b><br>"
                "Date: %{customdata[0]}<br>"
                "Rel Vol Ratio: %{y:.2f}x<br>"
                "Rel. Volume: %{customdata[2]:.2f}x (20D Avg)<br>"
                "Window Return (±5D): %{customdata[3]:+.2f}%<extra></extra>"
            )
        ), row=1, col=1)

    # Highlighted Shock Markers (Secondary) - Amber diamond with white border
    shocks2 = vol_analysis.get('secondary_shocks', [])
    if has_sec and shocks2:
        x_s2 = [s['date'] for s in shocks2]
        y_s2 = [s['vol_vs_benchmark_ratio'] for s in shocks2]
        customdata2 = [[
            s['date_str'],
            s['vol_vs_benchmark_ratio'],
            s['volume_multiple'],
            s['window_return_pct'],
            "Volume-Confirmed Vol Spike"
        ] for s in shocks2]

        fig.add_trace(go.Scatter(
            x=x_s2,
            y=y_s2,
            name=f"{p2_name} Shocks ({len(shocks2)})",
            mode="markers",
            marker=dict(
                symbol="diamond",
                size=12,
                color=c_shock_s,
                line=dict(width=2, color="#FFFFFF")
            ),
            customdata=customdata2,
            hovertemplate=(
                f"<b>⚡ {p2_name} Volatility Shock</b><br>"
                "Date: %{customdata[0]}<br>"
                "Rel Vol Ratio: %{y:.2f}x<br>"
                "Rel. Volume: %{customdata[2]:.2f}x (20D Avg)<br>"
                "Window Return (±5D): %{customdata[3]:+.2f}%<extra></extra>"
            )
        ), row=1, col=1)

    # -------------------------------------------------------------
    # ROW 2: Annualized Volatility (%)
    # -------------------------------------------------------------
    # Benchmark Annualized Vol
    fig.add_trace(go.Scatter(
        x=m1['bench_vol_20d_sma5'].index,
        y=m1['bench_vol_20d_sma5'],
        name=f"{b_name} Vol (%)",
        mode="lines",
        line=dict(color=c_bench, width=1.5, dash="dash"),
        hovertemplate=f"{b_name} Vol: %{{y:.1f}}%<extra></extra>"
    ), row=2, col=1)

    # Primary Annualized Vol
    fig.add_trace(go.Scatter(
        x=m1['vol_20d_sma5'].index,
        y=m1['vol_20d_sma5'],
        name=f"{p1_name} Vol (%)",
        mode="lines",
        line=dict(color=c_primary, width=1.8),
        hovertemplate=f"{p1_name} Vol: %{{y:.1f}}%<extra></extra>"
    ), row=2, col=1)

    # Secondary Annualized Vol (if pair mode)
    if has_sec and m2:
        fig.add_trace(go.Scatter(
            x=m2['vol_20d_sma5'].index,
            y=m2['vol_20d_sma5'],
            name=f"{p2_name} Vol (%)",
            mode="lines",
            line=dict(color=c_secondary, width=1.8),
            hovertemplate=f"{p2_name} Vol: %{{y:.1f}}%<extra></extra>"
        ), row=2, col=1)

    # -------------------------------------------------------------
    # ROW 3: Rel. Volume (x 20D Avg) Filtered Bar Chart
    # Resample to weekly max so bars remain crisp & legible over 15Y horizons
    # -------------------------------------------------------------
    def _prepare_volume_bars(series):
        if series is None or series.empty:
            return pd.Series(dtype=float)
        s = series.copy()
        try:
            if not isinstance(s.index, pd.DatetimeIndex):
                s.index = pd.to_datetime(s.index)
            s_w = s.resample('W').max()
        except Exception:
            s_w = s
        return s_w[s_w >= 2.0].dropna()

    vm1_filtered = _prepare_volume_bars(m1.get('rel_volume'))
    fig.add_trace(go.Bar(
        x=vm1_filtered.index,
        y=vm1_filtered,
        name=f"{p1_name} Rel. Volume (x 20D Avg)",
        visible=True,
        marker=dict(
            color="#38BDF8",
            line=dict(color="#38BDF8", width=1.5),
            opacity=0.85
        ),
        hovertemplate=f"<b>{p1_name} Rel. Volume:</b> %{{y:.2f}}x (20D Avg)<extra></extra>"
    ), row=3, col=1)

    if has_sec and m2:
        vm2_filtered = _prepare_volume_bars(m2.get('rel_volume'))
        fig.add_trace(go.Bar(
            x=vm2_filtered.index,
            y=vm2_filtered,
            name=f"{p2_name} Rel. Volume (x 20D Avg)",
            visible=True,
            marker=dict(
                color="#F59E0B",
                line=dict(color="#F59E0B", width=1.5),
                opacity=0.85
            ),
            hovertemplate=f"<b>{p2_name} Rel. Volume:</b> %{{y:.2f}}x (20D Avg)<extra></extra>"
        ), row=3, col=1)

    # Threshold dashed line at 2.0x
    fig.add_hline(
        y=2.0,
        line=dict(color="rgba(255, 255, 255, 0.20)", width=1.0, dash="dash"),
        row=3, col=1
    )

    # Layout styling matching InvestAide Dark Glass
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0D131F",
        plot_bgcolor="#0D131F",
        margin=dict(l=65, r=50, t=35, b=40),
        height=630,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            font=dict(size=10.5, family="Plus Jakarta Sans, sans-serif"),
            bgcolor="rgba(13, 19, 31, 0.7)",
            bordercolor="rgba(255, 255, 255, 0.08)",
            borderwidth=1
        ),
        hovermode="x unified",
        barmode="overlay",
        bargap=0.15
    )

    fig.update_yaxes(
        title_text="Vol Ratio (x)",
        row=1, col=1,
        gridcolor="rgba(255, 255, 255, 0.06)",
        tickfont=dict(size=10, family="JetBrains Mono, monospace")
    )
    fig.update_yaxes(
        title_text="Annualized Vol (%)",
        row=2, col=1,
        gridcolor="rgba(255, 255, 255, 0.06)",
        tickfont=dict(size=10, family="JetBrains Mono, monospace")
    )
    fig.update_yaxes(
        title_text="Rel. Vol (x)",
        row=3, col=1,
        gridcolor="rgba(255, 255, 255, 0.06)",
        tickfont=dict(size=9, family="JetBrains Mono, monospace", color="#94A3B8"),
        rangemode="nonnegative"
    )
    fig.update_xaxes(
        gridcolor="rgba(255, 255, 255, 0.06)",
        tickfont=dict(size=10, family="JetBrains Mono, monospace")
    )

    # Responsive and print-friendly configuration
    config = {
        'displayModeBar': True,
        'displaylogo': False,
        'responsive': True,
        'modeBarButtonsToRemove': ['lasso2d', 'select2d']
    }

    return fig.to_html(full_html=False, include_plotlyjs=False, config=config)


def extract_volatility_and_shocks_summary(vol_analysis):
    """
    Serializes the volatility metrics and detected idiosyncratic shocks into the target JSON structure:
    "volatility_and_shocks": {
      "benchmark_annualized_vol_median_pct": 14.2,
      "primary": { ... },
      "secondary": null | { ... }
    }
    """
    if not vol_analysis or not vol_analysis.get('primary_metrics'):
        return {
            "benchmark_annualized_vol_median_pct": None,
            "primary": None,
            "secondary": None
        }

    m1 = vol_analysis['primary_metrics']
    m2 = vol_analysis.get('secondary_metrics')
    has_sec = vol_analysis.get('has_secondary', False) and (m2 is not None)

    # Primary Security Object
    primary_shocks_clean = []
    for s in vol_analysis.get('primary_shocks', []):
        primary_shocks_clean.append({
            "date": s['date_str'],
            "month": s['month'],
            "vol_vs_benchmark_ratio": _safe_float(s['vol_vs_benchmark_ratio']),
            "median_vol_ratio": _safe_float(s['median_vol_ratio']),
            "volume_multiple": _safe_float(s['volume_multiple']),
            "window_return_pct": _safe_float(s['window_return_pct']),
            "shock_type": s['shock_type']
        })

    primary_obj = {
        "current_vol_pct": _safe_float(m1.get('current_vol_pct')),
        "median_vol_pct": _safe_float(m1.get('median_vol_pct')),
        "current_vol_vs_benchmark_ratio": _safe_float(m1.get('current_vol_ratio')),
        "median_vol_vs_benchmark_ratio": _safe_float(m1.get('median_vol_ratio')),
        "p95_vol_vs_benchmark_ratio": _safe_float(m1.get('p95_vol_ratio')),
        "idiosyncratic_shocks": primary_shocks_clean
    }

    # Secondary Security Object (if pair mode, else null)
    secondary_obj = None
    if has_sec and m2:
        secondary_shocks_clean = []
        for s in vol_analysis.get('secondary_shocks', []):
            secondary_shocks_clean.append({
                "date": s['date_str'],
                "month": s['month'],
                "vol_vs_benchmark_ratio": _safe_float(s['vol_vs_benchmark_ratio']),
                "median_vol_ratio": _safe_float(s['median_vol_ratio']),
                "volume_multiple": _safe_float(s['volume_multiple']),
                "window_return_pct": _safe_float(s['window_return_pct']),
                "shock_type": s['shock_type']
            })

        secondary_obj = {
            "current_vol_pct": _safe_float(m2.get('current_vol_pct')),
            "median_vol_pct": _safe_float(m2.get('median_vol_pct')),
            "current_vol_vs_benchmark_ratio": _safe_float(m2.get('current_vol_ratio')),
            "median_vol_vs_benchmark_ratio": _safe_float(m2.get('median_vol_ratio')),
            "p95_vol_vs_benchmark_ratio": _safe_float(m2.get('p95_vol_ratio')),
            "idiosyncratic_shocks": secondary_shocks_clean
        }

    return {
        "benchmark_annualized_vol_median_pct": _safe_float(vol_analysis.get('benchmark_median_vol_pct')),
        "primary": primary_obj,
        "secondary": secondary_obj
    }
