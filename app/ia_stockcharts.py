import pandas as pd
import yfinance as yf
import numpy as np
import pandas_datareader as wb
import datetime as dt
from plotly.offline import plot
from plotly.graph_objs import Scatter
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

try:
    import curl_cffi.requests
    _orig_cffi_init = curl_cffi.requests.Session.__init__
    def _new_cffi_init(self, *args, **kwargs):
        kwargs['verify'] = False
        _orig_cffi_init(self, *args, **kwargs)
    curl_cffi.requests.Session.__init__ = _new_cffi_init
except Exception:
    pass
import math
import copy
debug = 0
if debug :
    import ia_stock_index_info as ia_sinfo
    import bse_quarterly as bse_res
else:
    from . import ia_stock_index_info as ia_sinfo
    from . import bse_quarterly as bse_res
# import seaborn as sn
# import matplotlib as plt
from sklearn.cluster import KMeans
from sklearn.manifold import TSNE


### This file contains all the stock graph plot functions

def ia_plot_similar_stocks(stock_list, sdate, edate):
    amt_const = 1
    ticker_list = list(ia_sinfo.stock_name_code_map.keys())
    if stock_list and stock_list[0] in ticker_list:
        ticker_list.remove(stock_list[0])
    stock_count = len(ticker_list)

    full_prices_raw, act_sdate, missing_stocks, act_edate = ia_get_prices(stock_list + ticker_list, sdate, edate)
    if full_prices_raw is None or full_prices_raw.empty or full_prices_raw.dropna(how='all').empty:
        return pd.DataFrame(columns=["stock", "dist"])

    full_prices_norm = ia_norm_price(full_prices_raw)

    try:
        temp_write = pd.ExcelWriter(r".\similar.xlsx")
        full_prices_raw.to_excel(temp_write, sheet_name="raw prices")
        temp_write.save()
    except Exception:
        temp_write = None

    port_init_inv = amt_const
    print("#######", stock_count)
    for count in range(0, min(stock_count, max(0, len(full_prices_norm.columns) - 1))):
        try:
            full_prices_norm[full_prices_norm.columns[count + 1]] = full_prices_norm[full_prices_norm.columns[count + 1]] * port_init_inv
        except Exception:
            pass

    similar_df = get_similar_stock(full_prices_norm)
    if temp_write is not None:
        try:
            similar_df.to_excel(temp_write, sheet_name="analysis")
            temp_write.save()
        except Exception:
            pass

    return similar_df


def ia_plot_port_prices(stock_list, sdate, edate, y_scale, port_df):
    amt_const = 1
    ticker_list = port_df['ticker'].tolist() if (port_df is not None and 'ticker' in port_df.columns) else []
    stock_count = port_df.shape[0] if port_df is not None else 0

    full_prices_raw, act_sdate, missing_stocks, act_edate = ia_get_prices(stock_list + ticker_list, sdate, edate)

    if full_prices_raw is None or full_prices_raw.empty or full_prices_raw.dropna(how='all').empty or len(full_prices_raw) == 0:
        empty_plot = "<div><h6 style=\"text-align:center; color:orange;\">No stock price data available for the portfolio tickers.</h6></div>"
        empty_tbl = "<div><h6 style=\"text-align:center; color:orange;\">No data available.</h6></div>"
        msg = "Unable to fetch price data for the requested tickers."
        msg_list = missing_stocks if missing_stocks else "No data available"
        return (empty_plot, empty_tbl, empty_tbl, empty_plot, empty_plot, empty_plot, empty_plot, msg, msg_list)

    try:
        full_prices_raw = full_prices_raw.loc[act_sdate:]
    except Exception:
        pass

    try:
        full_prices_raw.to_excel(ia_sinfo.log_writer, sheet_name="port_fprraw")
        ia_sinfo.log_writer.save()
    except Exception:
        pass

    print("&&&&&&&&&&&&&&&&&&&&&&&&&&&")
    print(full_prices_raw.isnull().any(axis=1))
    try:
        max_ed = full_prices_raw[full_prices_raw.isnull().any(axis=1)].index[0]
        null_iloc = full_prices_raw.index.get_loc(max_ed)
        full_prices_norm = full_prices_raw.iloc[0: null_iloc - 1]
    except Exception:
        max_ed = full_prices_raw.index[-1] if len(full_prices_raw.index) > 0 else edate
        full_prices_norm = full_prices_raw
    print(full_prices_norm)
    print(act_sdate)
    print(max_ed)

    full_prices_norm = ia_norm_price(full_prices_norm)
    try:
        full_prices_norm.to_excel(ia_sinfo.log_writer, sheet_name="port_fprnorm")
        ia_sinfo.log_writer.save()
    except Exception:
        pass

    port_init_inv = (port_df['normwt'] * amt_const).tolist() if (port_df is not None and 'normwt' in port_df.columns) else [1] * stock_count
    print("#######", stock_count)
    for count in range(0, min(stock_count, max(0, len(full_prices_norm.columns) - 1))):
        try:
            full_prices_norm[full_prices_norm.columns[count + 1]] = full_prices_norm[full_prices_norm.columns[count + 1]] * port_init_inv[count]
        except Exception:
            pass

    Decline = 0.25
    combo_df = copy.deepcopy(full_prices_norm)
    if not combo_df.empty and len(combo_df.columns) > 0:
        combo_df['port'] = combo_df.sum(axis=1) - combo_df[combo_df.columns[0]]
        idx_port_df = pd.DataFrame()
        idx_port_df["index"] = combo_df[combo_df.columns[0]]
        idx_port_df["port"] = combo_df["port"]
    else:
        idx_port_df = pd.DataFrame()

    cycles = ia_get_cycle_dates(idx_port_df, Decline)
    prices_df = ia_populate_cycle(idx_port_df, cycles)

    pdiv2, pdiv1, pdiv_scat = ia_go_treeplot(full_prices_norm, "Portfolio Exposure")
    pdiv3 = ia_go_graph(idx_port_df, 1, 0, y_scale, "Relative performance over the period")

    norm_reset_df = ia_reset_returns(ia_norm_price(idx_port_df), cycles)
    norm_reset_df = ia_populate_cycle(norm_reset_df, cycles)

    pdiv4 = ia_go_graph(norm_reset_df, 1, 1, y_scale, "Relative performance across cycles")

    if prices_df is not None and not prices_df.empty and prices_df.shape[1] >= 2 and cycles:
        risk_metric_df = ia_calc_risk_metrics(prices_df[[prices_df.columns[0], prices_df.columns[1]]], cycles)
    else:
        risk_metric_df = pd.DataFrame()

    pdiv5 = ia_go_table(risk_metric_df, "s", "Relative performance & beta across cycles")
    pdiv6 = pdiv5

    if sdate != act_sdate:
        msg = "Analysis conducted from : " + (act_sdate.strftime("%d-%m-%Y") if hasattr(act_sdate, 'strftime') else str(act_sdate))
        msg_list = missing_stocks
    else:
        msg = "Analysis conducted from : " + (sdate.strftime("%d-%m-%Y") if hasattr(sdate, 'strftime') else str(sdate))
        msg_list = "All stock data available"

    return (pdiv4, pdiv5, pdiv6, pdiv3, pdiv2, pdiv1, pdiv_scat, msg, msg_list)


def ia_plot_prices(stock_list, sdate, edate, y_scale, cycle_type="bull_bear"):
    Decline = 0.25

    orig_prices_df, act_sdate, missing_stocks, act_edate = ia_get_prices(stock_list, sdate, edate)

    if orig_prices_df is None or orig_prices_df.empty or orig_prices_df.dropna(how='all').empty or len(orig_prices_df) == 0:
        empty_plot = "<div><h4 style=\"text-align:center; color:orange;\"><b>No stock price data available for the selected dates/tickers.</b></h4></div>"
        empty_tbl = "<div><h4 style=\"text-align:center; color:orange;\"><b>No data available.</b></h4></div>"
        missing_info = ", ".join([f"{k}: {v}" for k, v in missing_stocks.items()]) if missing_stocks else "No data retrieved"
        msg = f"Unable to fetch price data ({missing_info})"
        return (empty_plot, empty_tbl, empty_tbl, empty_plot, empty_plot, empty_plot, empty_plot, msg)

    try:
        prices_df = orig_prices_df.loc[act_sdate:act_edate]
    except Exception:
        prices_df = orig_prices_df

    if prices_df.empty:
        prices_df = orig_prices_df

    norm_prices_df = ia_norm_price(prices_df)
    cycles = ia_get_cycles_by_type(prices_df, cycle_type=cycle_type, bear_decline=Decline)

    prices_df = ia_populate_cycle(prices_df, cycles)
    norm_prices_df = ia_populate_cycle(norm_prices_df, cycles)

    # Retrieve earnings data and calculate daily Trailing TTM P/E and TTM PEG
    stk_ticker = stock_list[1] if len(stock_list) > 1 else None
    eps_df, ttm_eps, yoy_growth = (pd.DataFrame(), pd.Series(dtype=float), pd.Series(dtype=float))
    pe_data = None
    if stk_ticker and not prices_df.empty:
        eps_df, ttm_eps, yoy_growth = ia_get_earnings_data(stk_ticker)
        if not ttm_eps.empty and len(prices_df.columns) >= 2:
            pe_data = ia_calc_daily_pe(prices_df[prices_df.columns[1]], ttm_eps, yoy_growth=yoy_growth)

    tbl_div_eps = ia_go_eps_table(eps_df, prices_df[prices_df.columns[1]] if len(prices_df.columns) >= 2 else None, stk_ticker) if stk_ticker else ""
    plot_div_eps_growth = ia_go_growth_graph(eps_df, stk_ticker, sdate=act_sdate, edate=act_edate) if stk_ticker else ""

    pdiv1 = ia_go_graph(prices_df[[prices_df.columns[0], prices_df.columns[-1]]], 1, "r", y_scale, "Benchmark index", pe_data=None) if len(prices_df.columns) >= 2 else "<div></div>"
    pdiv2 = ia_go_graph(prices_df[[prices_df.columns[1], prices_df.columns[-1]]], 1, "b", y_scale, "Stock price", pe_data=pe_data) if len(prices_df.columns) >= 2 else "<div></div>"
    pdiv3 = ia_go_graph(norm_prices_df, 1, 0, y_scale, "Relative performance over the period", pe_data=pe_data)

    norm_reset_df = ia_reset_returns(ia_norm_price(prices_df), cycles)
    norm_reset_df = ia_populate_cycle(norm_reset_df, cycles)

    cycle_title_map = {
        "bull_bear": "market cycles",
        "calendar_year": "calendar years",
        "financial_year": "financial years",
        "quarterly": "quarters",
        "monthly": "months",
    }
    c_period_name = cycle_title_map.get(cycle_type, "cycles")
    pdiv4 = ia_go_graph(norm_reset_df, 1, 1, y_scale, f"Relative performance across {c_period_name}", pe_data=pe_data)

    if prices_df is not None and not prices_df.empty and len(prices_df.columns) >= 2 and cycles:
        risk_metric_df = ia_calc_risk_metrics(prices_df[[prices_df.columns[0], prices_df.columns[1]]], cycles, cycle_type=cycle_type)
    else:
        risk_metric_df = pd.DataFrame()

    pdiv5 = ia_go_table(risk_metric_df, "s", f"Relative performance & beta across {c_period_name}")

    try:
        orig_prices_df.to_csv('origprices.csv')
        prices_df.to_csv('prices.csv')
        norm_prices_df.to_csv('norm_prices.csv')
        norm_reset_df.to_csv('norm_reset.csv')
        risk_metric_df.to_csv('risk_metrics.csv')
    except Exception:
        pass

    if sdate != act_sdate:
        msg = "Analysis conducted from : " + (act_sdate.strftime("%d-%m-%Y") if hasattr(act_sdate, 'strftime') else str(act_sdate))
    else:
        msg = "Analysis conducted from : " + (sdate.strftime("%d-%m-%Y") if hasattr(sdate, 'strftime') else str(sdate))

    return (pdiv4, pdiv5, tbl_div_eps, plot_div_eps_growth, pdiv3, pdiv2, pdiv1, msg)


def ia_get_financials(comp, exch, sdate, edate):
    cname = ia_sinfo.stock_name_code_map.get(comp, [None, None, comp])[2]
    tbl_div_fin = ia_get_company_financials_widget(comp, sname=cname)
    msg = f"Audited corporate financial statements for {cname}"
    return (tbl_div_fin, "", msg)



def ia_reset_returns(ip_df, cycles):
    if ip_df is None or ip_df.empty or not cycles or len(ip_df.columns) == 0:
        return pd.DataFrame()

    op_df = pd.DataFrame(index=ip_df.index)

    mkt_col = ip_df.columns[0]
    stk_col = ip_df.columns[1] if len(ip_df.columns) > 1 and ip_df.columns[1] != 'Phase' else None

    for ctr in range(0, len(cycles)):
        op_df[mkt_col + " " + str(ctr)] = np.nan
        if stk_col:
            op_df[stk_col + " " + str(ctr)] = np.nan
            op_df["RelVal " + str(ctr)] = np.nan

    for ctr in range(0, len(cycles)):
        try:
            s_iloc = cycles[ctr][2]
            e_iloc = cycles[ctr][3]
            if s_iloc < len(ip_df.index):
                base_mkt = ip_df[mkt_col].iloc[s_iloc]
                if base_mkt != 0 and not pd.isna(base_mkt):
                    sub_mkt = 100 * ip_df[mkt_col].iloc[s_iloc:e_iloc + 1] / base_mkt
                    op_df.iloc[s_iloc:e_iloc + 1, op_df.columns.get_loc(mkt_col + " " + str(ctr))] = sub_mkt

                if stk_col:
                    base_stk = ip_df[stk_col].iloc[s_iloc]
                    if base_stk != 0 and not pd.isna(base_stk):
                        sub_stk = 100 * ip_df[stk_col].iloc[s_iloc:e_iloc + 1] / base_stk
                        op_df.iloc[s_iloc:e_iloc + 1, op_df.columns.get_loc(stk_col + " " + str(ctr))] = sub_stk

                        # Relative Value: Stock Index / Market Index ratio
                        if base_mkt != 0 and not pd.isna(base_mkt):
                            sub_rel = sub_stk / sub_mkt.replace(0, np.nan)
                            op_df.iloc[s_iloc:e_iloc + 1, op_df.columns.get_loc("RelVal " + str(ctr))] = sub_rel
        except Exception:
            pass

    return op_df


def ia_calc_risk_metrics(prices_df, cycles, cycle_type="bull_bear"):
    if prices_df is None or prices_df.empty or prices_df.shape[1] < 2 or not cycles or len(prices_df) == 0:
        return pd.DataFrame(columns=["Phase", "Start Date", "End Date", "beta", "Stock Return", "Market Return"])

    mkt_idx = prices_df.columns[0]
    stk_idx = prices_df.columns[1]

    sname_mkt = short_name(mkt_idx)
    sname_stk = short_name(stk_idx)

    rm_df = pd.DataFrame(
        columns=["Phase", "Start Date", "End Date", "beta", sname_stk + " Return", sname_mkt + " Return"],
        index=list(range(0, len(cycles) + 1))
    )
    for phase in range(0, len(cycles)):
        try:
            sd_iloc = cycles[phase][2]
            ed_iloc = min(len(prices_df.index) - 1, cycles[phase][3])

            if cycle_type == "bull_bear":
                dir_label = "Bull" if cycles[phase][1] == "U" else "Bear"
                rm_df.loc[phase, "Phase"] = f"Cycle {phase + 1} ({dir_label})"
            else:
                rm_df.loc[phase, "Phase"] = str(cycles[phase][0])

            if sd_iloc < len(prices_df.index):
                rm_df.loc[phase, "Start Date"] = prices_df.index[sd_iloc].date()
                rm_df.loc[phase, "End Date"] = prices_df.index[ed_iloc].date()

                mini_df = prices_df.iloc[sd_iloc:ed_iloc + 1]
                if not mini_df.empty and len(mini_df) > 1:
                    mini_ret_df = np.log(mini_df / mini_df.shift(1)).dropna()
                    cov_mtx = mini_ret_df.cov()
                    if not cov_mtx.empty and cov_mtx.shape[0] > 1 and cov_mtx.iloc[0, 0] != 0:
                        rm_df.loc[phase, "beta"] = np.round(cov_mtx.iloc[1, 0] / cov_mtx.iloc[0, 0], 2)

                s_start = prices_df[stk_idx].iloc[sd_iloc]
                s_end = prices_df[stk_idx].iloc[ed_iloc]
                m_start = prices_df[mkt_idx].iloc[sd_iloc]
                m_end = prices_df[mkt_idx].iloc[ed_iloc]

                if s_start != 0 and not pd.isna(s_start):
                    rm_df.loc[phase, sname_stk + " Return"] = round(np.round((s_end / s_start - 1), 3) * 100, 1)
                if m_start != 0 and not pd.isna(m_start):
                    rm_df.loc[phase, sname_mkt + " Return"] = round(np.round((m_end / m_start - 1), 3) * 100, 1)
        except Exception:
            pass

    try:
        rm_df.loc[len(cycles), "Phase"] = "Full Period"
        if len(prices_df.index) > 0:
            rm_df.loc[len(cycles), "Start Date"] = prices_df.index[0].date()
            rm_df.loc[len(cycles), "End Date"] = prices_df.index[-1].date()
            mini_df = prices_df
            if not mini_df.empty and len(mini_df) > 1:
                mini_ret_df = np.log(mini_df / mini_df.shift(1)).dropna()
                cov_mtx = mini_ret_df.cov()
                if not cov_mtx.empty and cov_mtx.shape[0] > 1 and cov_mtx.iloc[0, 0] != 0:
                    rm_df.loc[len(cycles), "beta"] = round(cov_mtx.iloc[1, 0] / cov_mtx.iloc[0, 0], 2)
            s_start = prices_df[stk_idx].iloc[0]
            s_end = prices_df[stk_idx].iloc[-1]
            m_start = prices_df[mkt_idx].iloc[0]
            m_end = prices_df[mkt_idx].iloc[-1]
            if s_start != 0 and not pd.isna(s_start):
                rm_df.loc[len(cycles), sname_stk + " Return"] = round(np.round((s_end / s_start - 1), 3) * 100, 1)
            if m_start != 0 and not pd.isna(m_start):
                rm_df.loc[len(cycles), sname_mkt + " Return"] = round(np.round((m_end / m_start - 1), 3) * 100, 1)
    except Exception:
        pass

    return rm_df


def ia_get_cycles_by_type(prices_df, cycle_type="bull_bear", bear_decline=0.25):
    if prices_df is None or prices_df.empty or len(prices_df) < 2 or len(prices_df.columns) == 0:
        return []

    if cycle_type == "bull_bear":
        return ia_get_cycle_dates(prices_df, bear_decline)

    d = pd.to_datetime(prices_df.index)
    n = len(d)
    if n < 2:
        return []

    cycles = []

    if cycle_type == "calendar_year":
        years = sorted(list(set(d.year)))
        prev_e = 0
        for i, y in enumerate(years):
            matching = np.where(d.year == y)[0]
            if len(matching) == 0:
                continue
            cur_e = matching[-1]
            cur_s = 0 if i == 0 else prev_e
            if cur_s < cur_e:
                m_start = prices_df.iloc[cur_s, 0]
                m_end = prices_df.iloc[cur_e, 0]
                p_dir = "D" if m_end < m_start else "U"
                cycles.append((f"CY {y}", p_dir, cur_s, cur_e))
                prev_e = cur_e

    elif cycle_type == "financial_year":
        fy_list = []
        for dt_val in d:
            fy_start = dt_val.year if dt_val.month >= 4 else dt_val.year - 1
            fy_list.append(fy_start)
        fy_series = pd.Series(fy_list, index=d)
        unique_fys = sorted(list(set(fy_list)))
        prev_e = 0
        for i, fy in enumerate(unique_fys):
            matching = np.where(fy_series == fy)[0]
            if len(matching) == 0:
                continue
            cur_e = matching[-1]
            cur_s = 0 if i == 0 else prev_e
            if cur_s < cur_e:
                m_start = prices_df.iloc[cur_s, 0]
                m_end = prices_df.iloc[cur_e, 0]
                p_dir = "D" if m_end < m_start else "U"
                cycles.append((f"FY {fy}-{str(fy + 1)[-2:]}", p_dir, cur_s, cur_e))
                prev_e = cur_e

    elif cycle_type == "quarterly":
        q_tuples = [(dt_val.year, (dt_val.month - 1) // 3 + 1) for dt_val in d]
        unique_qs = []
        for q in q_tuples:
            if q not in unique_qs:
                unique_qs.append(q)
        prev_e = 0
        for i, q in enumerate(unique_qs):
            matching = np.where([qt == q for qt in q_tuples])[0]
            if len(matching) == 0:
                continue
            cur_e = matching[-1]
            cur_s = 0 if i == 0 else prev_e
            if cur_s < cur_e:
                m_start = prices_df.iloc[cur_s, 0]
                m_end = prices_df.iloc[cur_e, 0]
                p_dir = "D" if m_end < m_start else "U"
                cycles.append((f"Q{q[1]} {q[0]}", p_dir, cur_s, cur_e))
                prev_e = cur_e

    elif cycle_type == "monthly":
        m_tuples = [(dt_val.year, dt_val.month) for dt_val in d]
        unique_ms = []
        for m in m_tuples:
            if m not in unique_ms:
                unique_ms.append(m)
        prev_e = 0
        for i, m in enumerate(unique_ms):
            matching = np.where([mt == m for mt in m_tuples])[0]
            if len(matching) == 0:
                continue
            cur_e = matching[-1]
            cur_s = 0 if i == 0 else prev_e
            if cur_s < cur_e:
                m_start = prices_df.iloc[cur_s, 0]
                m_end = prices_df.iloc[cur_e, 0]
                p_dir = "D" if m_end < m_start else "U"
                month_name = d[cur_e].strftime("%b %Y")
                cycles.append((month_name, p_dir, cur_s, cur_e))
                prev_e = cur_e

    return cycles


def ia_get_cycle_dates(prices_df, bear_decline):
    if prices_df is None or prices_df.empty or len(prices_df) < 2 or len(prices_df.columns) == 0:
        return []

    avg_period = 1
    bull_rise = 1 / (1 - bear_decline) - 1
    smooth_price_df = prices_df.iloc[:].rolling(window=avg_period).mean().copy()
    smooth_price_df.iloc[0:avg_period - 1] = prices_df.iloc[0:avg_period - 1]
    cname = smooth_price_df.columns[0]

    if smooth_price_df[cname].dropna().empty:
        return []

    try:
        idx_gmax = smooth_price_df[cname].idxmax()
        idx_gmin = smooth_price_df[cname].idxmin()
    except Exception:
        return []

    if pd.isna(idx_gmax) or pd.isna(idx_gmin):
        return []

    print("$$$$ Peaks in full period $$$$$ : ", idx_gmax, idx_gmin)

    if idx_gmax > idx_gmin:
        init_dir = "D"
    else:
        init_dir = "U"

    n_rows = smooth_price_df.shape[0]
    if n_rows == 0:
        return []

    watermark = [np.nan] * n_rows
    direction = [init_dir] * n_rows
    wmk2dt_ret = [np.nan] * n_rows
    toggle = [0] * n_rows

    series_vals = smooth_price_df[cname].values
    watermark[0] = series_vals[0]
    wmk2dt_ret[0] = 0

    toggle_list = [0]

    for count in range(1, n_rows):
        pret = wmk2dt_ret[count - 1]
        pdirec = direction[count - 1]

        if (pdirec == "U") and (pret > 0):
            watermark[count] = series_vals[count - 1]
        elif (pdirec == "D") and (pret < 0):
            watermark[count] = series_vals[count - 1]
        elif (pret >= bull_rise) or (pret <= -1 * bear_decline):
            watermark[count] = series_vals[count - 1]
        else:
            watermark[count] = watermark[count - 1]

        prev_wmk = watermark[count]
        if prev_wmk != 0 and not pd.isna(prev_wmk):
            wmk2dt_ret[count] = series_vals[count] / prev_wmk - 1
        else:
            wmk2dt_ret[count] = 0

        if watermark[count] == watermark[count - 1]:
            direction[count] = direction[count - 1]
        else:
            if watermark[count] < watermark[count - 1]:
                direction[count] = "D"
            else:
                direction[count] = "U"

        if direction[count] == direction[count - 1]:
            toggle[count] = 0
        else:
            toggle_list.append(count)
            toggle[count] = 1

    toggle[0] = 1
    toggle[-1] = 1
    toggle_list.append(n_rows - 1)

    smooth_price_df['watermark'] = watermark
    smooth_price_df['direction'] = direction
    smooth_price_df['wmk2dt_ret'] = wmk2dt_ret
    smooth_price_df['toggle'] = toggle

    phases = len(toggle_list) - 1
    if phases < 1:
        return []

    indices = []
    s_iloc = 0

    for phase in range(0, phases):
        pst_iloc = toggle_list[phase]
        pen_iloc = toggle_list[phase + 1]
        p_dir = direction[pen_iloc - 1]

        try:
            if p_dir == "U":
                p_peak = smooth_price_df[cname].iloc[pst_iloc:pen_iloc - 1].idxmax()
            else:
                p_peak = smooth_price_df[cname].iloc[pst_iloc:pen_iloc - 1].idxmin()

            e_iloc = smooth_price_df.index.get_loc(p_peak)
            indices.append((p_peak, p_dir, s_iloc, e_iloc))
            s_iloc = e_iloc
        except Exception:
            pass

    try:
        p_peak = smooth_price_df.index[pen_iloc]
        p_dir = direction[pen_iloc - 1]
        indices.append((p_peak, p_dir, s_iloc, pen_iloc))
    except Exception:
        pass

    cycles = indices
    last_ph = len(cycles)

    if last_ph >= 2 and cycles[last_ph - 1][1] == cycles[last_ph - 2][1]:
        tpl1 = (cycles[last_ph - 2][0], cycles[last_ph - 2][1], cycles[last_ph - 2][2], cycles[last_ph - 1][3])
        cycles.pop()
        cycles.pop()
        cycles.append(tpl1)

    return cycles


def ia_get_prices(stock_list, sdate, edate):
    ticker_list = stock_list
    stk_price_df = pd.DataFrame()

    missing_stocks = {}
    min_sdate = sdate
    max_edate = edate

    for ticker in ticker_list:
        temp_data = None
        # Try yfinance first
        try:
            downloaded = yf.download(ticker, start=sdate, end=edate, progress=False)
            if downloaded is not None and not downloaded.empty:
                if 'Adj Close' in downloaded.columns:
                    temp_data = downloaded['Adj Close']
                elif 'Close' in downloaded.columns:
                    temp_data = downloaded['Close']
                if isinstance(temp_data, pd.DataFrame):
                    temp_data = temp_data.iloc[:, 0]
        except Exception:
            temp_data = None

        # Fallback to Ticker history
        if temp_data is None or temp_data.empty:
            try:
                t = yf.Ticker(ticker)
                hist = t.history(start=sdate, end=edate)
                if hist is not None and not hist.empty:
                    if 'Adj Close' in hist.columns:
                        temp_data = hist['Adj Close']
                    elif 'Close' in hist.columns:
                        temp_data = hist['Close']
                    if isinstance(temp_data, pd.DataFrame):
                        temp_data = temp_data.iloc[:, 0]
            except Exception:
                temp_data = None

        # Fallback to pandas_datareader DataReader
        if temp_data is None or temp_data.empty:
            try:
                temp_data = wb.DataReader(ticker, data_source="yahoo", start=sdate, end=edate)['Adj Close']
                if isinstance(temp_data, pd.DataFrame):
                    temp_data = temp_data.iloc[:, 0]
            except Exception:
                temp_data = None

        if temp_data is not None and not temp_data.empty and len(temp_data) > 0:
            stk_price_df[ticker] = temp_data

            try:
                if temp_data.index[0] != sdate:
                    missing_stocks[ticker] = temp_data.index[0]
                    if min_sdate is None or min_sdate < temp_data.index[0]:
                        min_sdate = temp_data.index[0]

                if temp_data.index[-1] != edate:
                    missing_stocks[ticker] = temp_data.index[-1]
                    if max_edate is None or max_edate > temp_data.index[-1]:
                        max_edate = temp_data.index[-1]
            except Exception:
                pass
        else:
            missing_stocks[ticker] = "No data available"
            if stk_price_df.shape[0] > 0:
                stk_price_df[ticker] = np.nan
            else:
                stk_price_df[ticker] = pd.Series(dtype=float)

    return stk_price_df, min_sdate, missing_stocks, max_edate


def ia_norm_price(ip_df):
    if isinstance(ip_df, tuple):
        ip_df = ip_df[0]
    if ip_df is None or not isinstance(ip_df, (pd.DataFrame, pd.Series)) or ip_df.empty or len(ip_df) == 0:
        return ip_df
    try:
        first_row = ip_df.iloc[0]
        if isinstance(first_row, (pd.Series, np.ndarray)):
            first_row = first_row.replace(0, np.nan)
        elif first_row == 0:
            first_row = np.nan
        norm_df = 100 * ip_df / first_row
        return norm_df
    except Exception:
        return ip_df


def ia_populate_cycle(ip_df, cycles):
    if ip_df is None or ip_df.empty:
        return ip_df

    ip_df = ip_df.copy()
    phase_arr = [0] * ip_df.shape[0]
    if cycles:
        for count in range(0, len(cycles)):
            ph = 0 if cycles[count][1] == "U" else 1
            try:
                s_idx = max(0, cycles[count][2])
                e_idx = min(ip_df.shape[0], cycles[count][3])
                for i in range(s_idx, e_idx):
                    phase_arr[i] = ph
            except Exception:
                pass

    ip_df['Phase'] = phase_arr
    return ip_df


def ia_go_table(rm_df, size, title):
    if rm_df is None or rm_df.empty:
        return f'<div style="padding: 2.5rem; text-align: center; color: #64748B; font-family: \'Plus Jakarta Sans\', sans-serif; font-size: 0.8125rem;"><i class="fas fa-table mb-2" style="font-size: 1.5rem; opacity: 0.5; display: block;"></i>{title} (No Data Available)</div>'

    cols = list(rm_df.columns)
    max_h = '460px' if size == 's' else ('650px' if size == 'm' else '500px')

    html = [
        f'<div class="ia-grid-scroll-wrap" style="max-height: {max_h}; overflow-y: auto; overflow-x: auto; -webkit-overflow-scrolling: touch; border-radius: 8px; border: 1px solid rgba(30, 41, 59, 0.7); background: #0D131F;">',
        '  <style>',
        '    .ia-grid-scroll-wrap::-webkit-scrollbar { width: 8px; height: 8px; }',
        '    .ia-grid-scroll-wrap::-webkit-scrollbar-track { background: #090D15; border-radius: 4px; }',
        '    .ia-grid-scroll-wrap::-webkit-scrollbar-thumb { background: #1E293B; border-radius: 4px; border: 1px solid rgba(255, 255, 255, 0.08); }',
        '    .ia-grid-scroll-wrap::-webkit-scrollbar-thumb:hover { background: #38BDF8; }',
        '    .ia-grid-tbl { width: 100%; border-collapse: separate; border-spacing: 0; font-family: "JetBrains Mono", monospace; font-size: 0.8125rem; margin: 0; }',
        '    .ia-grid-tbl th { position: sticky; top: 0; z-index: 10; background: #131B2B; color: #38A9F6; font-family: "Plus Jakarta Sans", sans-serif; font-weight: 700; font-size: 0.72rem; letter-spacing: 0.05em; text-transform: uppercase; padding: 11px 14px; text-align: center; border-bottom: 2px solid rgba(56, 169, 246, 0.4); border-right: 1px solid rgba(255, 255, 255, 0.08); white-space: nowrap; box-shadow: 0 2px 4px rgba(0,0,0,0.3); }',
        '    .ia-grid-tbl th:last-child { border-right: none; }',
        '    .ia-grid-tbl td { padding: 9px 14px; text-align: center; color: #F8FAFC; border-bottom: 1px solid rgba(255, 255, 255, 0.06); border-right: 1px solid rgba(255, 255, 255, 0.06); white-space: nowrap; }',
        '    .ia-grid-tbl td:last-child { border-right: none; }',
        '    .ia-grid-tbl tbody tr:hover td { background: rgba(56, 169, 246, 0.08); }',
        '    .ia-grid-tbl tr.ia-row-full-period td { background: rgba(14, 140, 228, 0.18) !important; font-weight: 700; color: #38BDF8 !important; border-top: 2px solid rgba(56, 169, 246, 0.5); border-bottom: none; position: sticky; bottom: 0; z-index: 5; }',
        '  </style>',
        '  <table class="ia-grid-tbl">',
        '    <thead>',
        '      <tr>'
    ]

    for col in cols:
        html.append(f'        <th>{col}</th>')
    html.append('      </tr>')
    html.append('    </thead>')
    html.append('    <tbody>')

    for idx, row in rm_df.iterrows():
        is_full = (str(row.get('Phase', '')).strip() == 'Full Period')
        row_cls = ' class="ia-row-full-period"' if is_full else ''
        html.append(f'      <tr{row_cls}>')
        for col in cols:
            val = row[col]
            if pd.isna(val):
                disp = "-"
                style = ""
            elif isinstance(val, (int, float, np.number)):
                if 'Return' in col:
                    color = '#34D399' if val > 0 else ('#F43F5E' if val < 0 else '#F8FAFC')
                    disp = f"{val:.1f}"
                    style = f' style="color: {color};"'
                elif col.lower() == 'beta':
                    disp = f"{val:.2f}"
                    style = ""
                else:
                    disp = f"{val:.2f}" if isinstance(val, float) else f"{val}"
                    style = ""
            else:
                disp = str(val)
                style = ""
            html.append(f'        <td{style}>{disp}</td>')
        html.append('      </tr>')

    html.append('    </tbody>')
    html.append('  </table>')
    html.append('</div>')
    return '\n'.join(html)


def ia_get_earnings_data(ticker_symbol):
    """
    Retrieves quarterly earnings dates and Reported EPS using yfinance,
    computes rolling 4-quarter TTM EPS, and returns (earnings_df, ttm_eps_series).
    """
    if not ticker_symbol:
        return pd.DataFrame(), pd.Series(dtype=float), pd.Series(dtype=float)

    try:
        t = yf.Ticker(ticker_symbol)
        ed = t.get_earnings_dates(limit=100)
        try:
            if ed is not None and len(ed) >= 95:
                ed_prev = t.get_earnings_dates(limit=100, offset=100)
                if ed_prev is not None and not ed_prev.empty:
                    ed = pd.concat([ed, ed_prev])
        except Exception:
            pass
        if ed is None or ed.empty or 'Reported EPS' not in ed.columns:
            return pd.DataFrame(), pd.Series(dtype=float), pd.Series(dtype=float)

        # Normalize datetime index to tz-naive
        ed_clean = ed.copy()
        ed_clean.index = pd.to_datetime(ed_clean.index).normalize()
        try:
            ed_clean.index = ed_clean.index.tz_localize(None)
        except TypeError:
            pass

        # De-duplicate index if any
        ed_clean = ed_clean[~ed_clean.index.duplicated(keep='last')]

        # Extract Reported EPS
        rep_eps = ed_clean['Reported EPS'].dropna().sort_index(ascending=True)
        if rep_eps.empty:
            return pd.DataFrame(), pd.Series(dtype=float), pd.Series(dtype=float)

        # Compute rolling 4-quarter TTM EPS
        ttm_eps = rep_eps.rolling(window=4).sum().dropna()

        # Compute quarterly YoY growth in rolling 4-quarter TTM EPS (compared with 4 quarters prior)
        yoy_growth = (ttm_eps.pct_change(periods=4) * 100).dropna()

        # Build clean earnings dataframe sorted descending
        eps_records = []
        for dt_idx, val in rep_eps.sort_index(ascending=False).items():
            t_val = ttm_eps.get(dt_idx, np.nan)
            g_val = yoy_growth.get(dt_idx, np.nan)
            q_num = (dt_idx.month - 1) // 3 + 1
            eps_records.append({
                "Date": dt_idx,
                "Quarter": f"Q{q_num} FY{str(dt_idx.year)[2:]}",
                "Announcement Date": dt_idx.strftime("%d %b %Y"),
                "Reported EPS": val,
                "TTM EPS": t_val,
                "YoY Growth": g_val
            })

        eps_df = pd.DataFrame(eps_records)
        return eps_df, ttm_eps, yoy_growth
    except Exception:
        return pd.DataFrame(), pd.Series(dtype=float), pd.Series(dtype=float)


def ia_calc_daily_pe(stock_series, ttm_eps, yoy_growth=None):
    """
    Forward-fills rolling 4-quarter TTM EPS onto the stock's daily price calendar,
    computes daily Trailing P/E = Price / TTM EPS, and calculates historical valuation benchmarks:
    median PE, +1 SD upper band, -1 SD lower band.
    Optionally computes daily Trailing TTM PEG = daily PE / YoY EPS Growth Rate.
    """
    if stock_series is None or stock_series.empty or ttm_eps is None or ttm_eps.empty:
        return None

    try:
        # Normalize stock index
        stk_clean = stock_series.copy()
        stk_clean.index = pd.to_datetime(stk_clean.index).normalize()
        try:
            stk_clean.index = stk_clean.index.tz_localize(None)
        except TypeError:
            pass

        # Normalize ttm_eps index
        ttm_clean = ttm_eps.copy()
        ttm_clean.index = pd.to_datetime(ttm_clean.index).normalize()
        try:
            ttm_clean.index = ttm_clean.index.tz_localize(None)
        except TypeError:
            pass
        ttm_clean = ttm_clean[~ttm_clean.index.duplicated(keep='last')]

        # Reindex, forward-fill, and backward-fill for earliest periods onto stock calendar
        daily_ttm_eps = ttm_clean.reindex(stk_clean.index, method='ffill').bfill()
        daily_pe = (stk_clean / daily_ttm_eps.replace(0, np.nan)).dropna()

        if daily_pe.empty:
            return None

        # Valuation corridor statistics
        med_pe = float(daily_pe.median())
        sd_pe = float(daily_pe.std()) if len(daily_pe) > 1 else 0.0
        up_pe = med_pe + sd_pe
        lo_pe = max(0.0, med_pe - sd_pe)

        res = {
            "daily_pe": daily_pe,
            "median_pe": med_pe,
            "std_pe": sd_pe,
            "upper_pe": up_pe,
            "lower_pe": lo_pe
        }

        # Daily Trailing TTM PEG = daily PE / YoY EPS Growth Rate (%)
        if yoy_growth is not None and not yoy_growth.empty:
            growth_clean = yoy_growth.copy()
            growth_clean.index = pd.to_datetime(growth_clean.index).normalize()
            try:
                growth_clean.index = growth_clean.index.tz_localize(None)
            except TypeError:
                pass
            growth_clean = growth_clean[~growth_clean.index.duplicated(keep='last')]
            daily_growth = growth_clean.reindex(stk_clean.index, method='ffill').bfill()

            daily_peg = daily_pe / daily_growth.replace(0, np.nan)
            daily_peg_plot = daily_peg.copy()
            # Mask out non-positive growth for clean visualization
            daily_peg_plot[daily_growth <= 0] = np.nan
            daily_peg_plot = daily_peg_plot.clip(lower=0, upper=15)

            # Historical Median TTM PEG on positive growth data
            valid_peg = daily_peg[daily_growth > 0].dropna()
            med_peg = float(valid_peg.median()) if not valid_peg.empty else None

            res["daily_growth"] = daily_growth
            res["daily_peg"] = daily_peg
            res["daily_peg_plot"] = daily_peg_plot
            res["median_peg"] = med_peg

        return res
    except Exception:
        return None


def ia_go_eps_table(eps_df, stock_series, ticker_symbol):
    """
    Renders the Quarterly & Trailing (TTM) EPS Ledger in a scrollable, sticky-header table.
    Shows: Fiscal Quarter, Announcement Date, Reported Qtr EPS, Rolling 4Q TTM EPS, YoY TTM Growth (%), Stock Price on Date, Trailing P/E, TTM PEG.
    """
    sname = short_name(ticker_symbol)
    if eps_df is None or eps_df.empty:
        return f'<div style="padding: 2.5rem; text-align: center; color: #64748B; font-family: \'Plus Jakarta Sans\', sans-serif; font-size: 0.8125rem;"><i class="fas fa-file-invoice-dollar mb-2" style="font-size: 1.5rem; opacity: 0.5; display: block;"></i>Quarterly & TTM EPS Ledger for {sname} (No Data Available)</div>'

    # Align stock price to announcement date
    stk_lookup = stock_series.copy() if stock_series is not None and not stock_series.empty else pd.Series(dtype=float)
    if not stk_lookup.empty:
        stk_lookup.index = pd.to_datetime(stk_lookup.index).normalize()
        try:
            stk_lookup.index = stk_lookup.index.tz_localize(None)
        except TypeError:
            pass

    html = [
        '<div class="ia-grid-scroll-wrap" style="max-height: 460px; overflow-y: auto; overflow-x: auto; -webkit-overflow-scrolling: touch; border-radius: 8px; border: 1px solid rgba(30, 41, 59, 0.7); background: #0D131F;">',
        '  <style>',
        '    .ia-grid-scroll-wrap::-webkit-scrollbar { width: 8px; height: 8px; }',
        '    .ia-grid-scroll-wrap::-webkit-scrollbar-track { background: #090D15; border-radius: 4px; }',
        '    .ia-grid-scroll-wrap::-webkit-scrollbar-thumb { background: #1E293B; border-radius: 4px; border: 1px solid rgba(255, 255, 255, 0.08); }',
        '    .ia-grid-scroll-wrap::-webkit-scrollbar-thumb:hover { background: #38BDF8; }',
        '    .ia-eps-tbl { width: 100%; border-collapse: separate; border-spacing: 0; font-family: "JetBrains Mono", monospace; font-size: 0.8125rem; margin: 0; }',
        '    .ia-eps-tbl th { position: sticky; top: 0; z-index: 10; background: #131B2B; color: #38A9F6; font-family: "Plus Jakarta Sans", sans-serif; font-weight: 700; font-size: 0.72rem; letter-spacing: 0.05em; text-transform: uppercase; padding: 11px 14px; text-align: center; border-bottom: 2px solid rgba(56, 169, 246, 0.4); border-right: 1px solid rgba(255, 255, 255, 0.08); white-space: nowrap; box-shadow: 0 2px 4px rgba(0,0,0,0.3); }',
        '    .ia-eps-tbl th:last-child { border-right: none; }',
        '    .ia-eps-tbl td { padding: 9px 14px; text-align: center; color: #F8FAFC; border-bottom: 1px solid rgba(255, 255, 255, 0.06); border-right: 1px solid rgba(255, 255, 255, 0.06); white-space: nowrap; }',
        '    .ia-eps-tbl td:last-child { border-right: none; }',
        '    .ia-eps-tbl tbody tr:hover td { background: rgba(56, 169, 246, 0.08); }',
        '  </style>',
        '  <table class="ia-eps-tbl">',
        '    <thead>',
        '      <tr>',
        '        <th>Fiscal Quarter</th>',
        '        <th>Announcement Date</th>',
        f'        <th>{sname} Qtr EPS</th>',
        f'        <th>Rolling 4Q TTM EPS</th>',
        '        <th>YoY TTM Growth</th>',
        f'        <th>{sname} Price</th>',
        '        <th>Trailing P/E</th>',
        '        <th>TTM PEG</th>',
        '      </tr>',
        '    </thead>',
        '    <tbody>'
    ]

    for _, row in eps_df.iterrows():
        dt_val = row['Date']
        qtr_str = row['Quarter']
        ann_date = row['Announcement Date']
        rep_eps = row['Reported EPS']
        ttm_val = row['TTM EPS']
        g_val = row.get('YoY Growth', np.nan)

        # Price on date
        p_val = np.nan
        if not stk_lookup.empty:
            p_val = stk_lookup.asof(dt_val)

        p_str = f"₹{p_val:.2f}" if pd.notna(p_val) else "-"
        rep_str = f"₹{rep_eps:.2f}" if pd.notna(rep_eps) else "-"
        ttm_str = f"₹{ttm_val:.2f}" if pd.notna(ttm_val) else "-"

        if pd.notna(g_val):
            g_prefix = "+" if g_val > 0 else ""
            g_color = "#34D399" if g_val >= 0 else "#EF4444"
            g_str = f"{g_prefix}{g_val:.1f}%"
        else:
            g_color = "#94A3B8"
            g_str = "-"

        if pd.notna(p_val) and pd.notna(ttm_val) and ttm_val > 0:
            pe_calc = p_val / ttm_val
            pe_str = f"{pe_calc:.1f}x"
        else:
            pe_calc = np.nan
            pe_str = "-"

        if pd.notna(pe_calc) and pd.notna(g_val) and g_val > 0:
            peg_calc = pe_calc / g_val
            peg_str = f"{peg_calc:.2f}x"
            peg_style = ' style="color: #2DD4BF; font-weight: 700;"'
        else:
            peg_str = "-"
            peg_style = ""

        html.append('      <tr>')
        html.append(f'        <td style="color: #38BDF8; font-weight: 700;">{qtr_str}</td>')
        html.append(f'        <td>{ann_date}</td>')
        html.append(f'        <td style="color: #34D399; font-weight: 600;">{rep_str}</td>')
        html.append(f'        <td style="color: #FACC15; font-weight: 700;">{ttm_str}</td>')
        html.append(f'        <td style="color: {g_color}; font-weight: 700;">{g_str}</td>')
        html.append(f'        <td>{p_str}</td>')
        html.append(f'        <td style="color: #C084FC; font-weight: 700;">{pe_str}</td>')
        html.append(f'        <td{peg_style}>{peg_str}</td>')
        html.append('      </tr>')

    html.append('    </tbody>')
    html.append('  </table>')
    html.append('</div>')
    return '\n'.join(html)


def ia_go_growth_graph(eps_df, ticker_symbol, sdate=None, edate=None):
    """
    Renders the Quarterly YoY Growth in Rolling 4-Quarter TTM EPS chart.
    Features:
    - Positive expansion quarters in emerald green (#10B981)
    - Contraction quarters in crimson red (#EF4444)
    - Trendline with markers connecting quarterly points (#38BDF8)
    - Dotted historical median growth rate benchmark line (#94A3B8)
    """
    sname = short_name(ticker_symbol)
    if eps_df is None or eps_df.empty or 'YoY Growth' not in eps_df.columns:
        fig = go.Figure()
        fig.update_layout(
            title=f"Quarterly YoY TTM EPS Growth for {sname} (No Data Available)",
            paper_bgcolor="#0D131F",
            font=dict(color="#94A3B8")
        )
        return plot(fig, output_type='div')

    q_df = eps_df.dropna(subset=['YoY Growth']).sort_values('Date', ascending=True).copy()
    if sdate:
        try:
            s_dt = pd.to_datetime(sdate).normalize()
            q_df = q_df[q_df['Date'] >= s_dt]
        except Exception:
            pass
    if edate:
        try:
            e_dt = pd.to_datetime(edate).normalize()
            q_df = q_df[q_df['Date'] <= e_dt]
        except Exception:
            pass

    if q_df.empty:
        fig = go.Figure()
        fig.update_layout(
            title=f"Quarterly YoY TTM EPS Growth for {sname} (No Data in Range)",
            paper_bgcolor="#0D131F",
            font=dict(color="#94A3B8")
        )
        return plot(fig, output_type='div')

    bar_colors = ['#10B981' if v >= 0 else '#EF4444' for v in q_df['YoY Growth']]
    med_growth = float(q_df['YoY Growth'].median())

    fig = go.Figure()
    # 1. Bar trace
    fig.add_trace(go.Bar(
        x=q_df['Date'],
        y=q_df['YoY Growth'],
        marker=dict(color=bar_colors, line=dict(color='rgba(255, 255, 255, 0.08)', width=1)),
        name="Quarterly YoY Growth",
        customdata=np.stack((q_df['Quarter'], q_df['TTM EPS'], q_df['Announcement Date']), axis=-1),
        hovertemplate="<b>%{customdata[0]}</b> (%{customdata[2]})<br>YoY TTM EPS Growth: <b>%{y:.2f}%</b><br>Rolling 4Q TTM EPS: ₹%{customdata[1]:.2f}<extra></extra>"
    ))

    # 2. Trendline
    fig.add_trace(go.Scatter(
        x=q_df['Date'],
        y=q_df['YoY Growth'],
        mode='lines+markers',
        line=dict(color='#38BDF8', width=2, shape='spline'),
        marker=dict(size=5, color='#F8FAFC', line=dict(color='#0284C7', width=1)),
        name="Growth Trend",
        hoverinfo="skip"
    ))

    # 3. Median growth reference line
    fig.add_trace(go.Scatter(
        x=q_df['Date'],
        y=[med_growth] * len(q_df),
        mode='lines',
        line=dict(color='#94A3B8', width=1.5, dash='dot'),
        name=f"Historical Median ({med_growth:.1f}%)",
        hovertemplate=f"Historical Median Growth: {med_growth:.1f}%<extra></extra>"
    ))

    fig.update_layout(
        title=dict(
            text=f"Quarterly YoY Growth in Rolling 4-Quarter TTM EPS ({sname})",
            font=dict(color="#F8FAFC", size=13),
            x=0.01,
            y=0.98
        ),
        paper_bgcolor="#0D131F",
        plot_bgcolor="#090D15",
        font=dict(color="#F8FAFC", family="Plus Jakarta Sans, sans-serif"),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color="#94A3B8", size=10, family="JetBrains Mono, monospace")
        ),
        margin=dict(l=35, r=40, t=65, b=35),
        height=380,
        hovermode="x unified"
    )
    fig.update_xaxes(
        mirror=True,
        gridcolor="rgba(30, 41, 59, 0.7)",
        zerolinecolor="#1E293B",
        tickfont=dict(color="#94A3B8", size=10, family="JetBrains Mono, monospace")
    )
    fig.update_yaxes(
        title=dict(text="YoY Growth Rate (%)", font=dict(color="#38BDF8", size=11, family="Plus Jakarta Sans, sans-serif")),
        mirror=True,
        gridcolor="rgba(30, 41, 59, 0.7)",
        zeroline=True,
        zerolinecolor="#475569",
        tickfont=dict(color="#38BDF8", size=10, family="JetBrains Mono, monospace")
    )

    return plot(fig, output_type='div')


# ---------------------------------------------------------------------------
# Corporate Financial Statements Engine (yfinance)
# ---------------------------------------------------------------------------

INCOME_STATEMENT_SCHEMA = {
    "Revenue & Cost": [
        ("Total Revenue", ["Total Revenue"]),
        ("Operating Revenue", ["Operating Revenue", "Total Revenue"]),
        ("Cost Of Revenue", ["Cost Of Revenue", "Reconciled Cost Of Revenue"]),
        ("Gross Profit", ["Gross Profit"]),
    ],
    "Operating Line": [
        ("Operating Expense", ["Operating Expense"]),
        ("EBITDA", ["EBITDA", "Normalized EBITDA"]),
        ("EBIT", ["EBIT"]),
        ("Operating Income", ["Operating Income"]),
    ],
    "Bottom Line": [
        ("Pretax Income", ["Pretax Income"]),
        ("Tax Provision", ["Tax Provision"]),
        ("Net Income Common Stockholders", ["Net Income Common Stockholders"]),
        ("Net Income Continuous Operations", ["Net Income Continuous Operations", "Net Income From Continuing Operation Net Minority Interest"]),
    ],
    "Per-Share & Share Counts": [
        ("Basic EPS", ["Basic EPS"]),
        ("Diluted EPS", ["Diluted EPS"]),
        ("Basic Average Shares", ["Basic Average Shares"]),
        ("Diluted Average Shares", ["Diluted Average Shares"]),
    ]
}

BALANCE_SHEET_SCHEMA = {
    "Assets": [
        ("Total Assets", ["Total Assets"]),
        ("Current Assets", ["Current Assets"]),
        ("Cash And Cash Equivalents", ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"]),
        ("Net PPE", ["Net PPE"]),
        ("Goodwill And Other Intangible Assets", ["Goodwill And Other Intangible Assets"]),
    ],
    "Liabilities": [
        ("Total Liabilities Net Minority Interest", ["Total Liabilities Net Minority Interest"]),
        ("Current Liabilities", ["Current Liabilities"]),
        ("Total Debt", ["Total Debt"]),
        ("Long Term Debt", ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"]),
        ("Current Debt", ["Current Debt", "Current Debt And Capital Lease Obligation"]),
    ],
    "Equity & Capital Structure": [
        ("Stockholders Equity", ["Stockholders Equity"]),
        ("Common Stock Equity", ["Common Stock Equity"]),
        ("Retained Earnings", ["Retained Earnings"]),
        ("Ordinary Shares Number", ["Ordinary Shares Number"]),
        ("Share Issued", ["Share Issued"]),
    ],
    "Liquidity & Working Capital": [
        ("Working Capital", ["Working Capital"]),
        ("Net Debt", ["Net Debt"]),
        ("Invested Capital", ["Invested Capital"]),
    ]
}

CASH_FLOW_SCHEMA = {
    "Operating Activities": [
        ("Operating Cash Flow", ["Operating Cash Flow"]),
        ("Cash Flow From Continuing Operating Activities", ["Cash Flow From Continuing Operating Activities", "Operating Cash Flow"]),
        ("Depreciation Amortization Depletion", ["Depreciation Amortization Depletion", "Depreciation And Amortization", "Depreciation"]),
        ("Change In Working Capital", ["Change In Working Capital"]),
    ],
    "Investing Activities": [
        ("Investing Cash Flow", ["Investing Cash Flow"]),
        ("Capital Expenditure", ["Capital Expenditure"]),
        ("Net PPE Purchase And Sale", ["Net PPE Purchase And Sale"]),
        ("Net Business Purchase And Sale", ["Net Business Purchase And Sale"]),
    ],
    "Financing Activities": [
        ("Financing Cash Flow", ["Financing Cash Flow"]),
        ("Cash Dividends Paid", ["Cash Dividends Paid"]),
        ("Repurchase Of Capital Stock", ["Repurchase Of Capital Stock", "Common Stock Payments"]),
        ("Common Stock Issuance / Payments", ["Common Stock Issuance", "Issuance Of Capital Stock", "Common Stock Payments", "Net Common Stock Issuance"]),
        ("Long Term Debt Issuance / Payments", ["Long Term Debt Issuance", "Issuance Of Debt", "Long Term Debt Payments", "Repayment Of Debt", "Net Issuance Payments Of Debt"]),
    ],
    "Free Cash Flow & Net Cash": [
        ("Free Cash Flow", ["Free Cash Flow"]),
        ("Changes In Cash", ["Changes In Cash"]),
        ("End Cash Position", ["End Cash Position"]),
    ]
}

KEY_HIGHLIGHT_ROWS = {
    "Total Revenue", "Gross Profit", "Operating Income", "Net Income Common Stockholders",
    "Total Assets", "Total Liabilities Net Minority Interest", "Stockholders Equity",
    "Operating Cash Flow", "Free Cash Flow"
}


def _get_stmt(ticker_obj, primary_attr, fallback_attr=None):
    try:
        df = getattr(ticker_obj, primary_attr, None)
        if df is not None and not df.empty:
            return df
    except Exception:
        pass
    if fallback_attr:
        try:
            df = getattr(ticker_obj, fallback_attr, None)
            if df is not None and not df.empty:
                return df
        except Exception:
            pass
    return pd.DataFrame()


def ia_extract_statement(raw_df, schema, max_cols=4):
    if raw_df is None or raw_df.empty:
        return pd.DataFrame()
    # Select the most recent max_cols periods, then arrange chronologically (old on left, latest on right)
    recent_cols = sorted(raw_df.columns, reverse=True)[:max_cols]
    chronological_cols = sorted(recent_cols)
    df = raw_df[chronological_cols].copy()

    rows = []
    row_labels = []

    for section_name, items in schema.items():
        row_labels.append(f"__SECTION__{section_name}")
        rows.append({col: np.nan for col in df.columns})

        for display_name, candidates in items:
            val_series = None
            for cand in candidates:
                if cand in df.index:
                    val_series = df.loc[cand]
                    break

            if val_series is None and display_name == "Net Debt":
                if "Total Debt" in df.index and "Cash And Cash Equivalents" in df.index:
                    val_series = df.loc["Total Debt"] - df.loc["Cash And Cash Equivalents"]
            elif val_series is None and display_name == "Free Cash Flow":
                if "Operating Cash Flow" in df.index and "Capital Expenditure" in df.index:
                    val_series = df.loc["Operating Cash Flow"] - df.loc["Capital Expenditure"]

            row_labels.append(display_name)
            if val_series is not None:
                rows.append(val_series.to_dict())
            else:
                rows.append({col: np.nan for col in df.columns})

    return pd.DataFrame(rows, index=row_labels)


def ia_format_stmt_col_date(dt_val, is_quarterly=False):
    try:
        ts = pd.to_datetime(dt_val)
        if is_quarterly:
            return f"{ts.strftime('%b %Y')}<br><span style='font-size:0.68rem; color:#64748B;'>{ts.strftime('%d %b %Y')}</span>"
        else:
            return f"FY {ts.year}<br><span style='font-size:0.68rem; color:#64748B;'>{ts.strftime('%d %b %Y')}</span>"
    except Exception:
        return str(dt_val)


def ia_format_stmt_val(label, val):
    if pd.isna(val) or val is None:
        return "-"
    try:
        num = float(val)
        if "EPS" in label:
            return f"₹{num:.2f}"
        elif "Shares" in label or "Share Issued" in label:
            cr_shares = num / 1e7
            return f"{cr_shares:,.2f} Cr"
        else:
            in_cr = num / 1e7
            prefix = "₹" if in_cr >= 0 else "-₹"
            return f"{prefix}{abs(in_cr):,.1f} Cr"
    except Exception:
        return str(val)


def ia_render_statement_table(df, is_quarterly=False, is_cash_flow=False):
    if df is None or df.empty or len(df.columns) == 0:
        if is_cash_flow and is_quarterly:
            return '''
            <div style="padding: 2.5rem 1.5rem; text-align: center; color: #94A3B8; background: #0D131F;">
              <i class="fas fa-file-invoice-dollar mb-2" style="font-size: 1.6rem; color: #38BDF8; opacity: 0.85; display: block;"></i>
              <span style="font-weight: 700; color: #F8FAFC; font-size: 0.875rem;">Quarterly Cash Flow Statements Not Published</span>
              <p style="margin-top: 8px; font-size: 0.8125rem; color: #94A3B8; max-width: 560px; margin-left: auto; margin-right: auto; line-height: 1.6;">
                Indian corporate reporting under SEBI regulations mandates annual Cash Flow statements. Please select <a href="javascript:void(0)" onclick="iaSwitchStmt(document.querySelector('[data-stmt=inc]'), 'inc')" style="color: #38BDF8; font-weight: 700; text-decoration: underline;">Income Statement</a> or <a href="javascript:void(0)" onclick="iaSwitchStmt(document.querySelector('[data-stmt=bs]'), 'bs')" style="color: #38BDF8; font-weight: 700; text-decoration: underline;">Balance Sheet</a> to view Quarterly performance, or view Cash Flow in <a href="javascript:void(0)" onclick="iaSwitchPeriod(document.querySelector('[data-period=ann]'), 'ann')" style="color: #34D399; font-weight: 700; text-decoration: underline;">Annual (4 Years)</a> mode.
              </p>
            </div>
            '''
        return '<div style="padding: 2.5rem; text-align: center; color: #64748B; font-size: 0.8125rem;">No Financial Statement Data Available</div>'

    html = [
        '<div class="table-responsive" style="max-height: 480px; overflow-y: auto; overflow-x: auto; border: 1px solid rgba(30, 41, 59, 0.7); border-radius: 8px; background: #0D131F;">',
        '  <table class="table" style="margin: 0; width: 100%; border-collapse: separate; border-spacing: 0; font-family: \'JetBrains Mono\', monospace; font-size: 0.8125rem;">',
        '    <thead>',
        '      <tr>',
        '        <th style="position: sticky; top: 0; left: 0; z-index: 20; background: #131B2B; color: #38BDF8; font-family: \'Plus Jakarta Sans\', sans-serif; font-weight: 700; font-size: 0.72rem; letter-spacing: 0.05em; text-transform: uppercase; padding: 11px 16px; border-bottom: 2px solid rgba(56, 189, 248, 0.4); border-right: 1px solid rgba(255, 255, 255, 0.08); min-width: 280px; box-shadow: 2px 0 4px rgba(0,0,0,0.3);">Key Line Item</th>'
    ]

    for col in df.columns:
        c_label = ia_format_stmt_col_date(col, is_quarterly=is_quarterly)
        html.append(f'        <th style="position: sticky; top: 0; z-index: 10; background: #131B2B; color: #38BDF8; font-family: \'Plus Jakarta Sans\', sans-serif; font-weight: 700; font-size: 0.72rem; letter-spacing: 0.05em; text-transform: uppercase; padding: 11px 16px; text-align: right; border-bottom: 2px solid rgba(56, 189, 248, 0.4); border-right: 1px solid rgba(255, 255, 255, 0.08); white-space: nowrap; min-width: 140px;">{c_label}</th>')

    html.append('      </tr>')
    html.append('    </thead>')
    html.append('    <tbody>')

    for row_name in df.index:
        if row_name.startswith("__SECTION__"):
            sec_title = row_name.replace("__SECTION__", "")
            colspan = len(df.columns) + 1
            html.append('      <tr style="background: rgba(56, 189, 248, 0.08);">')
            html.append(f'        <td colspan="{colspan}" style="padding: 8px 16px; color: #38BDF8; font-family: \'Plus Jakarta Sans\', sans-serif; font-weight: 800; font-size: 0.75rem; letter-spacing: 0.06em; text-transform: uppercase; border-bottom: 1px solid rgba(56, 189, 248, 0.2);"><i class="fas fa-caret-right mr-2" style="opacity: 0.7;"></i>{sec_title}</td>')
            html.append('      </tr>')
            continue

        is_highlight = row_name in KEY_HIGHLIGHT_ROWS
        row_bg = 'background: rgba(14, 140, 228, 0.08);' if is_highlight else ''
        text_color = '#38BDF8' if is_highlight else '#F8FAFC'
        font_weight = 'font-weight: 700;' if is_highlight else 'font-weight: 500;'

        html.append(f'      <tr style="{row_bg}">')
        html.append(f'        <td style="position: sticky; left: 0; z-index: 5; background: {"#111928" if is_highlight else "#0D131F"}; padding: 9px 16px; color: {text_color}; {font_weight} border-bottom: 1px solid rgba(255, 255, 255, 0.06); border-right: 1px solid rgba(255, 255, 255, 0.08); white-space: nowrap; box-shadow: 2px 0 4px rgba(0,0,0,0.2);">{row_name}</td>')

        for col in df.columns:
            val = df.loc[row_name, col]
            val_str = ia_format_stmt_val(row_name, val)
            num_color = '#34D399' if is_highlight else '#E2E8F0'
            if str(val_str).startswith("-₹"):
                num_color = '#F87171'
            html.append(f'        <td style="padding: 9px 16px; text-align: right; color: {num_color}; {font_weight} border-bottom: 1px solid rgba(255, 255, 255, 0.06); border-right: 1px solid rgba(255, 255, 255, 0.06); white-space: nowrap;">{val_str}</td>')

        html.append('      </tr>')

    html.append('    </tbody>')
    html.append('  </table>')
    html.append('</div>')
    return '\n'.join(html)


def ia_go_annual_financial_trends_chart(ticker_symbol, sname=None, raw_inc=None, raw_bs=None, raw_cf=None):
    if not ticker_symbol or str(ticker_symbol).startswith("^"):
        return ""
    if not sname:
        try:
            sname = ia_sinfo.stock_name_code_map.get(ticker_symbol, [None, None, ticker_symbol])[2]
        except Exception:
            sname = str(ticker_symbol).replace(".NS", "").replace(".BO", "")

    try:
        if raw_inc is None or raw_bs is None or raw_cf is None:
            t = yf.Ticker(ticker_symbol)
            if raw_inc is None:
                raw_inc = _get_stmt(t, 'income_stmt', 'financials')
            if raw_bs is None:
                raw_bs = _get_stmt(t, 'balance_sheet')
            if raw_cf is None:
                raw_cf = _get_stmt(t, 'cash_flow', 'cashflow')
    except Exception as e:
        print(f"Error fetching data for annual trends chart ({ticker_symbol}): {e}")
        return ""

    if raw_inc is None or raw_inc.empty:
        return ""

    # 4 most recent annual periods in chronological order (old on left, latest on right)
    recent_cols = sorted(raw_inc.columns, reverse=True)[:4]
    years_cols = sorted(recent_cols)

    year_labels = []
    rev_vals = []
    op_vals = []
    pat_vals = []
    debt_vals = []
    ocf_vals = []

    for c in years_cols:
        ts = pd.to_datetime(c)
        year_labels.append(f"FY {ts.year}")

        # 1. Revenues
        rev = np.nan
        for cand in ["Total Revenue", "Operating Revenue"]:
            if cand in raw_inc.index and c in raw_inc.columns and not pd.isna(raw_inc.loc[cand, c]):
                rev = float(raw_inc.loc[cand, c]) / 1e7
                break
        rev_vals.append(rev if not np.isnan(rev) else 0)

        # 2. Operating Profits
        op = np.nan
        for cand in ["Operating Income", "EBIT"]:
            if cand in raw_inc.index and c in raw_inc.columns and not pd.isna(raw_inc.loc[cand, c]):
                op = float(raw_inc.loc[cand, c]) / 1e7
                break
        op_vals.append(op if not np.isnan(op) else 0)

        # 3. Net Profit
        pat = np.nan
        for cand in ["Net Income Common Stockholders", "Net Income Continuous Operations"]:
            if cand in raw_inc.index and c in raw_inc.columns and not pd.isna(raw_inc.loc[cand, c]):
                pat = float(raw_inc.loc[cand, c]) / 1e7
                break
        pat_vals.append(pat if not np.isnan(pat) else 0)

        # 4. Debt
        debt = np.nan
        if raw_bs is not None and not raw_bs.empty:
            for cand in ["Total Debt", "Long Term Debt"]:
                if cand in raw_bs.index and c in raw_bs.columns and not pd.isna(raw_bs.loc[cand, c]):
                    debt = float(raw_bs.loc[cand, c]) / 1e7
                    break
        debt_vals.append(debt if not np.isnan(debt) else 0)

        # 5. Operating Cash Flows
        ocf = np.nan
        if raw_cf is not None and not raw_cf.empty:
            for cand in ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"]:
                if cand in raw_cf.index and c in raw_cf.columns and not pd.isna(raw_cf.loc[cand, c]):
                    ocf = float(raw_cf.loc[cand, c]) / 1e7
                    break
        ocf_vals.append(ocf if not np.isnan(ocf) else 0)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=year_labels,
        y=rev_vals,
        name="Total Revenue",
        marker_color="#38BDF8",
        hovertemplate="<b>Total Revenue</b>: ₹%{y:,.1f} Cr<br>Period: %{x}<extra></extra>"
    ))

    fig.add_trace(go.Bar(
        x=year_labels,
        y=op_vals,
        name="Operating Profit (EBIT)",
        marker_color="#FACC15",
        hovertemplate="<b>Operating Profit</b>: ₹%{y:,.1f} Cr<br>Period: %{x}<extra></extra>"
    ))

    fig.add_trace(go.Bar(
        x=year_labels,
        y=pat_vals,
        name="Net Profit (PAT)",
        marker_color="#34D399",
        hovertemplate="<b>Net Profit</b>: ₹%{y:,.1f} Cr<br>Period: %{x}<extra></extra>"
    ))

    fig.add_trace(go.Bar(
        x=year_labels,
        y=debt_vals,
        name="Total Debt",
        marker_color="#FB7185",
        hovertemplate="<b>Total Debt</b>: ₹%{y:,.1f} Cr<br>Period: %{x}<extra></extra>"
    ))

    fig.add_trace(go.Bar(
        x=year_labels,
        y=ocf_vals,
        name="Operating Cash Flow",
        marker_color="#C084FC",
        hovertemplate="<b>Operating Cash Flow</b>: ₹%{y:,.1f} Cr<br>Period: %{x}<extra></extra>"
    ))

    fig.update_layout(
        barmode='group',
        bargroupgap=0.12,
        bargap=0.25,
        title=dict(
            text=f"Annual Financial Trajectory — 4-Year Growth ({sname})",
            font=dict(color="#F8FAFC", size=13),
            x=0.01,
            y=0.98
        ),
        paper_bgcolor="#0D131F",
        plot_bgcolor="#090D15",
        font=dict(color="#F8FAFC", family="Plus Jakarta Sans, sans-serif"),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color="#94A3B8", size=10, family="JetBrains Mono, monospace")
        ),
        margin=dict(l=45, r=30, t=65, b=35),
        height=400,
        hovermode="x unified"
    )

    fig.update_xaxes(
        mirror=True,
        gridcolor="rgba(30, 41, 59, 0.7)",
        zerolinecolor="#1E293B",
        tickfont=dict(color="#94A3B8", size=11, family="JetBrains Mono, monospace")
    )

    fig.update_yaxes(
        title=dict(text="Amount (₹ Crores)", font=dict(color="#38BDF8", size=11, family="Plus Jakarta Sans, sans-serif")),
        mirror=True,
        gridcolor="rgba(30, 41, 59, 0.7)",
        zeroline=True,
        zerolinecolor="#475569",
        tickfont=dict(color="#38BDF8", size=10, family="JetBrains Mono, monospace")
    )

    return plot(fig, output_type='div')


def ia_get_company_financials_widget(ticker_symbol, sname=None):
    if not ticker_symbol or str(ticker_symbol).startswith("^"):
        return ""

    if not sname:
        try:
            sname = ia_sinfo.stock_name_code_map.get(ticker_symbol, [None, None, ticker_symbol])[2]
        except Exception:
            sname = str(ticker_symbol).replace(".NS", "").replace(".BO", "")

    try:
        t = yf.Ticker(ticker_symbol)
        raw_inc_ann = _get_stmt(t, 'income_stmt', 'financials')
        raw_inc_qtr = _get_stmt(t, 'quarterly_income_stmt', 'quarterly_financials')
        raw_bs_ann = _get_stmt(t, 'balance_sheet')
        raw_bs_qtr = _get_stmt(t, 'quarterly_balance_sheet')
        raw_cf_ann = _get_stmt(t, 'cash_flow', 'cashflow')
        raw_cf_qtr = _get_stmt(t, 'quarterly_cash_flow')
    except Exception as e:
        print(f"Error fetching statements for {ticker_symbol}: {e}")
        return ""

    # Check if any data exists
    all_empty = all(df is None or df.empty for df in [raw_inc_ann, raw_inc_qtr, raw_bs_ann, raw_bs_qtr, raw_cf_ann, raw_cf_qtr])
    if all_empty:
        return f'''
        <div class="card" style="background: #0D131F; border: 1px solid rgba(30, 41, 59, 0.8); border-radius: 12px; margin-bottom: 24px;">
          <div class="card-header" style="background: #111928; border-bottom: 1px solid rgba(30, 41, 59, 0.8); padding: 16px 20px;">
            <h4 style="font-size: 0.9375rem; font-weight: 700; color: #F8FAFC; margin: 0;">
              Corporate Financial Statements ({sname})
            </h4>
          </div>
          <div class="card-body" style="padding: 2.5rem; text-align: center; color: #64748B; font-size: 0.8125rem;">
            <i class="fas fa-file-invoice-dollar mb-2" style="font-size: 1.5rem; opacity: 0.5; display: block;"></i>
            No financial statement filings found on yfinance for {sname} ({ticker_symbol}).
          </div>
        </div>
        '''

    # Extract 4 Annual periods and 5 Quarters (arranged chronologically)
    inc_ann = ia_extract_statement(raw_inc_ann, INCOME_STATEMENT_SCHEMA, max_cols=4)
    inc_qtr = ia_extract_statement(raw_inc_qtr, INCOME_STATEMENT_SCHEMA, max_cols=5)
    bs_ann = ia_extract_statement(raw_bs_ann, BALANCE_SHEET_SCHEMA, max_cols=4)
    bs_qtr = ia_extract_statement(raw_bs_qtr, BALANCE_SHEET_SCHEMA, max_cols=5)
    cf_ann = ia_extract_statement(raw_cf_ann, CASH_FLOW_SCHEMA, max_cols=4)
    cf_qtr = ia_extract_statement(raw_cf_qtr, CASH_FLOW_SCHEMA, max_cols=5)

    h_inc_ann = ia_render_statement_table(inc_ann, is_quarterly=False)
    h_inc_qtr = ia_render_statement_table(inc_qtr, is_quarterly=True)
    h_bs_ann = ia_render_statement_table(bs_ann, is_quarterly=False)
    h_bs_qtr = ia_render_statement_table(bs_qtr, is_quarterly=True)
    h_cf_ann = ia_render_statement_table(cf_ann, is_quarterly=False)
    h_cf_qtr = ia_render_statement_table(cf_qtr, is_quarterly=True, is_cash_flow=True)

    widget_html = f'''
    <style>
      .btn-stmt-tab {{
        background: transparent;
        border: none;
        color: #94A3B8;
        padding: 6px 14px;
        border-radius: 6px;
        font-size: 0.78rem;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s ease;
        display: inline-flex;
        align-items: center;
        gap: 6px;
      }}
      .btn-stmt-tab:hover {{
        color: #F8FAFC;
      }}
      .btn-stmt-tab.active {{
        background: #0284C7;
        color: #FFFFFF;
        box-shadow: 0 2px 6px rgba(2, 132, 199, 0.4);
      }}
      .btn-period-pill {{
        background: transparent;
        border: none;
        color: #94A3B8;
        padding: 5px 14px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s ease;
        display: inline-flex;
        align-items: center;
      }}
      .btn-period-pill:hover {{
        color: #F8FAFC;
      }}
      .btn-period-pill.active {{
        background: #38BDF8;
        color: #090D15;
        font-weight: 700;
      }}
      .ia-stmt-pane {{
        display: none;
      }}
      .ia-stmt-pane.active {{
        display: block;
      }}
    </style>

    <div class="card" style="background: #0D131F; border: 1px solid rgba(30, 41, 59, 0.8); border-radius: 12px; margin-bottom: 24px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4); overflow: hidden;">
      <div class="card-header" style="background: #111928; border-bottom: 1px solid rgba(30, 41, 59, 0.8); padding: 14px 20px; display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 14px;">
        <div style="display: flex; align-items: center; gap: 10px;">
          <i class="fas fa-file-invoice-dollar" style="color: #38BDF8; font-size: 1.15rem;"></i>
          <h4 style="font-size: 0.9375rem; font-weight: 700; color: #F8FAFC; margin: 0;">
            Corporate Financial Statements ({sname})
          </h4>
          <span style="background: rgba(56, 189, 248, 0.15); color: #38BDF8; border: 1px solid rgba(56, 189, 248, 0.3); padding: 3px 8px; border-radius: 6px; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase;">
            Audited Filings
          </span>
        </div>

        <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
          <!-- Statement Tabs -->
          <div id="stmt-tabs-group" style="display: inline-flex; border-radius: 8px; background: #090D15; padding: 3px; border: 1px solid rgba(255, 255, 255, 0.08);">
            <button type="button" class="btn-stmt-tab active" data-stmt="inc" onclick="iaSwitchStmt(this, 'inc')">
              <i class="fas fa-chart-line"></i> Income Statement
            </button>
            <button type="button" class="btn-stmt-tab" data-stmt="bs" onclick="iaSwitchStmt(this, 'bs')">
              <i class="fas fa-balance-scale"></i> Balance Sheet
            </button>
            <button type="button" class="btn-stmt-tab" data-stmt="cf" onclick="iaSwitchStmt(this, 'cf')">
              <i class="fas fa-money-bill-wave"></i> Cash Flow
            </button>
          </div>

          <!-- Period Toggle (Annual vs Quarterly) -->
          <div id="period-pills-group" style="display: inline-flex; border-radius: 9999px; background: #090D15; padding: 3px; border: 1px solid rgba(56, 189, 248, 0.2);">
            <button type="button" class="btn-period-pill active" data-period="ann" onclick="iaSwitchPeriod(this, 'ann')">Annual (4 Years)</button>
            <button type="button" class="btn-period-pill" data-period="qtr" onclick="iaSwitchPeriod(this, 'qtr')">Quarterly (5 Quarters)</button>
          </div>
        </div>
      </div>

      <div class="card-body p-0">
        <!-- Income Statement Panes -->
        <div id="pane-inc-ann" class="ia-stmt-pane active">
          {h_inc_ann}
        </div>
        <div id="pane-inc-qtr" class="ia-stmt-pane">
          {h_inc_qtr}
        </div>

        <!-- Balance Sheet Panes -->
        <div id="pane-bs-ann" class="ia-stmt-pane">
          {h_bs_ann}
        </div>
        <div id="pane-bs-qtr" class="ia-stmt-pane">
          {h_bs_qtr}
        </div>

        <!-- Cash Flow Panes -->
        <div id="pane-cf-ann" class="ia-stmt-pane">
          {h_cf_ann}
        </div>
        <div id="pane-cf-qtr" class="ia-stmt-pane">
          {h_cf_qtr}
        </div>
      </div>

      <div style="padding: 10px 20px; background: #090D15; border-top: 1px solid rgba(30, 41, 59, 0.6); font-size: 0.72rem; color: #64748B; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
        <span><i class="fas fa-info-circle mr-1" style="color: #38BDF8;"></i> All monetary values in ₹ Crores (divided by 10,000,000) unless per-share (EPS). Share counts in Crores.</span>
        <span>Source: Official yfinance corporate filings</span>
      </div>
    </div>

    <script>
      window.iaActiveStmt = 'inc';
      window.iaActivePeriod = 'ann';

      function iaUpdateStmtPanes() {{
        var panes = document.querySelectorAll('.ia-stmt-pane');
        for (var i = 0; i < panes.length; i++) {{
          panes[i].classList.remove('active');
          panes[i].style.display = 'none';
        }}
        var activeId = 'pane-' + window.iaActiveStmt + '-' + window.iaActivePeriod;
        var activeEl = document.getElementById(activeId);
        if (activeEl) {{
          activeEl.classList.add('active');
          activeEl.style.display = 'block';
        }}
      }}

      function iaSwitchStmt(btn, stmt) {{
        if (!btn) return;
        window.iaActiveStmt = stmt;
        // If clicking Cash Flow and currently on Quarterly, auto-switch to Annual (4 Years)
        if (stmt === 'cf' && window.iaActivePeriod === 'qtr') {{
          window.iaActivePeriod = 'ann';
          var annPill = document.querySelector('[data-period="ann"]');
          if (annPill) {{
            document.querySelectorAll('.btn-period-pill').forEach(function(b) {{ b.classList.remove('active'); }});
            annPill.classList.add('active');
          }}
        }}
        document.querySelectorAll('.btn-stmt-tab').forEach(function(b) {{ b.classList.remove('active'); }});
        btn.classList.add('active');
        iaUpdateStmtPanes();
      }}

      function iaSwitchPeriod(btn, period) {{
        if (!btn) return;
        window.iaActivePeriod = period;
        // If clicking Quarterly and currently on Cash Flow, auto-switch to Income Statement
        if (period === 'qtr' && window.iaActiveStmt === 'cf') {{
          window.iaActiveStmt = 'inc';
          var incBtn = document.querySelector('[data-stmt="inc"]');
          if (incBtn) {{
            document.querySelectorAll('.btn-stmt-tab').forEach(function(b) {{ b.classList.remove('active'); }});
            incBtn.classList.add('active');
          }}
        }}
        document.querySelectorAll('.btn-period-pill').forEach(function(b) {{ b.classList.remove('active'); }});
        btn.classList.add('active');
        iaUpdateStmtPanes();
      }}
    </script>
    '''
    return widget_html


def ia_get_security_expectations_widget(ticker_symbol, sname=None):
    if not ticker_symbol or str(ticker_symbol).startswith("^"):
        return ""

    if not sname:
        try:
            sname = ia_sinfo.stock_name_code_map.get(ticker_symbol, [None, None, ticker_symbol])[2]
        except Exception:
            sname = str(ticker_symbol).replace(".NS", "").replace(".BO", "")

    info = {}
    fast_info = {}
    try:
        t = yf.Ticker(ticker_symbol)
        try:
            info = t.info or {}
            if not isinstance(info, dict):
                info = {}
        except Exception as e:
            print(f"Warning: t.info failed for {ticker_symbol}: {e}")
            info = {}

        try:
            fast_info = t.fast_info or {}
        except Exception:
            fast_info = {}
    except Exception as e:
        print(f"Error initializing ticker for {ticker_symbol}: {e}")
        return ""

    # 1. Market Cap (with fast_info fallback)
    market_cap = info.get("marketCap")
    if market_cap is None and fast_info:
        try:
            market_cap = fast_info.get("marketCap") or fast_info.get("market_cap")
        except Exception:
            pass

    # Current Market Price (with fast_info fallback)
    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    if current_price is None and fast_info:
        try:
            current_price = fast_info.get("lastPrice") or fast_info.get("last_price")
        except Exception:
            pass

    # 2. One Year Forward EPS Estimate
    forward_eps = info.get("forwardEps")
    # 3. Forward P/E
    forward_pe = info.get("forwardPE")
    # 4. TTM P/E
    trailing_pe = info.get("trailingPE")
    # Analyst Target Prices
    target_low = info.get("targetLowPrice")
    target_high = info.get("targetHighPrice")
    target_median = info.get("targetMedianPrice")
    target_mean = info.get("targetMeanPrice")

    # Direct Yahoo quoteSummary fallback if consensus fields are missing
    if all(x is None for x in [forward_eps, forward_pe, target_mean, target_low]):
        try:
            import json
            import urllib.request
            q_url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker_symbol}?modules=financialData,defaultKeyStatistics,summaryDetail"
            q_req = urllib.request.Request(q_url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
            })
            with urllib.request.urlopen(q_req, timeout=4) as q_resp:
                q_data = json.loads(q_resp.read().decode('utf-8'))
                res_list = q_data.get('quoteSummary', {}).get('result', [])
                if res_list:
                    res_dict = res_list[0]
                    fin = res_dict.get('financialData', {})
                    stat = res_dict.get('defaultKeyStatistics', {})
                    sm = res_dict.get('summaryDetail', {})
                    def _raw(d, k):
                        v = d.get(k)
                        return v.get('raw') if isinstance(v, dict) else v

                    if market_cap is None:
                        market_cap = _raw(sm, 'marketCap') or _raw(stat, 'marketCap')
                    if current_price is None:
                        current_price = _raw(fin, 'currentPrice')
                    if forward_eps is None:
                        forward_eps = _raw(stat, 'forwardEps')
                    if forward_pe is None:
                        forward_pe = _raw(stat, 'forwardPE') or _raw(sm, 'forwardPE')
                    if trailing_pe is None:
                        trailing_pe = _raw(sm, 'trailingPE')
                    if target_low is None:
                        target_low = _raw(fin, 'targetLowPrice')
                    if target_high is None:
                        target_high = _raw(fin, 'targetHighPrice')
                    if target_median is None:
                        target_median = _raw(fin, 'targetMedianPrice')
                    if target_mean is None:
                        target_mean = _raw(fin, 'targetMeanPrice')
        except Exception:
            pass

    # Fallback for trailing_pe if None
    if trailing_pe is None:
        trailing_eps = info.get("trailingEps")
        if current_price and trailing_eps:
            try:
                cp = float(current_price)
                te = float(trailing_eps)
                if te > 0:
                    trailing_pe = cp / te
            except Exception:
                pass

    # If all items are None, don't show an empty card
    if all(x is None for x in [market_cap, forward_eps, forward_pe, trailing_pe, target_low, target_high, target_median, target_mean]):
        return ""

    # Formatter helpers
    def fmt_cur(val):
        if val is None or pd.isna(val):
            return "-"
        try:
            return f"₹{float(val):,.2f}"
        except Exception:
            return str(val)

    # Market Cap formatting in Crores
    mcap_str = "-"
    if market_cap is not None and not pd.isna(market_cap):
        try:
            cr_val = float(market_cap) / 1e7
            mcap_str = f"₹{cr_val:,.1f} Cr"
        except Exception:
            mcap_str = str(market_cap)

    # Forward EPS formatting
    fwd_eps_str = "-"
    if forward_eps is not None and not pd.isna(forward_eps):
        try:
            fwd_eps_str = f"₹{float(forward_eps):.2f}"
        except Exception:
            fwd_eps_str = str(forward_eps)

    # Forward P/E formatting
    fwd_pe_str = "-"
    if forward_pe is not None and not pd.isna(forward_pe):
        try:
            fwd_pe_str = f"{float(forward_pe):.2f}x"
        except Exception:
            fwd_pe_str = str(forward_pe)

    # TTM P/E formatting
    ttm_pe_str = "-"
    if trailing_pe is not None and not pd.isna(trailing_pe):
        try:
            ttm_pe_str = f"{float(trailing_pe):.2f}x"
        except Exception:
            ttm_pe_str = str(trailing_pe)

    # Target Prices formatting
    t_mean_str = fmt_cur(target_mean)
    t_median_str = fmt_cur(target_median)
    t_low_str = fmt_cur(target_low)
    t_high_str = fmt_cur(target_high)
    cur_price_str = fmt_cur(current_price)

    upside_badge = ""
    if current_price and target_mean:
        try:
            cp = float(current_price)
            tm = float(target_mean)
            if cp > 0:
                upside_pct = (tm / cp - 1) * 100
                if upside_pct >= 0:
                    upside_badge = f'<span style="color: #34D399; font-weight: 700; font-size: 0.75rem;"><i class="fas fa-arrow-up mr-1"></i>+{upside_pct:.1f}% Upside</span>'
                else:
                    upside_badge = f'<span style="color: #F87171; font-weight: 700; font-size: 0.75rem;"><i class="fas fa-arrow-down mr-1"></i>{upside_pct:.1f}% Downside</span>'
        except Exception:
            pass

    cur_price_sub = f"CMP: {cur_price_str}" if current_price else ""
    if upside_badge:
        cur_price_sub += f" &bull; {upside_badge}"

    html = f'''
    <div class="card" style="background: #0D131F; border: 1px solid rgba(30, 41, 59, 0.8); border-radius: 12px; margin-top: 0px; margin-bottom: 24px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35); overflow: hidden;">
      <div class="card-header" style="background: #111928; border-bottom: 1px solid rgba(30, 41, 59, 0.8); padding: 12px 18px; display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <i class="fas fa-crosshairs" style="color: #38BDF8; font-size: 1rem;"></i>
          <h4 style="font-size: 0.875rem; font-weight: 700; color: #F8FAFC; margin: 0;">
            Security Profile & Market Expectations ({sname})
          </h4>
          <span style="background: rgba(56, 189, 248, 0.15); color: #38BDF8; border: 1px solid rgba(56, 189, 248, 0.3); padding: 2px 7px; border-radius: 6px; font-size: 0.68rem; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase;">
            Consensus Projections
          </span>
        </div>
        <div style="font-size: 0.75rem; color: #94A3B8; font-family: 'JetBrains Mono', monospace;">
          {cur_price_sub}
        </div>
      </div>

      <div class="card-body" style="padding: 16px 18px;">
        <!-- Top 4 Primary Metric Cards -->
        <div class="row" style="margin: 0 -8px;">
          <!-- 1. Market Cap -->
          <div class="col-lg-3 col-sm-6" style="padding: 6px 8px;">
            <div style="background: #090D15; border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 8px; padding: 12px 14px; height: 100%;">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                <span style="font-size: 0.7rem; color: #94A3B8; text-transform: uppercase; font-weight: 700; letter-spacing: 0.04em;">Market Cap</span>
                <i class="fas fa-coins" style="color: #38BDF8; opacity: 0.85; font-size: 0.85rem;"></i>
              </div>
              <div style="font-size: 1.15rem; font-weight: 800; color: #F8FAFC; font-family: 'JetBrains Mono', monospace;">
                {mcap_str}
              </div>
              <div style="font-size: 0.68rem; color: #64748B; margin-top: 3px;">
                Total Market Capitalization
              </div>
            </div>
          </div>

          <!-- 2. One Year Forward EPS Estimate -->
          <div class="col-lg-3 col-sm-6" style="padding: 6px 8px;">
            <div style="background: #090D15; border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 8px; padding: 12px 14px; height: 100%;">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                <span style="font-size: 0.7rem; color: #94A3B8; text-transform: uppercase; font-weight: 700; letter-spacing: 0.04em;">1-Yr Forward EPS</span>
                <i class="fas fa-chart-line" style="color: #34D399; opacity: 0.85; font-size: 0.85rem;"></i>
              </div>
              <div style="font-size: 1.15rem; font-weight: 800; color: #34D399; font-family: 'JetBrains Mono', monospace;">
                {fwd_eps_str}
              </div>
              <div style="font-size: 0.68rem; color: #64748B; margin-top: 3px;">
                Consensus 12M Forward EPS
              </div>
            </div>
          </div>

          <!-- 3. Forward P/E -->
          <div class="col-lg-3 col-sm-6" style="padding: 6px 8px;">
            <div style="background: #090D15; border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 8px; padding: 12px 14px; height: 100%;">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                <span style="font-size: 0.7rem; color: #94A3B8; text-transform: uppercase; font-weight: 700; letter-spacing: 0.04em;">Forward P/E</span>
                <i class="fas fa-percentage" style="color: #C084FC; opacity: 0.85; font-size: 0.85rem;"></i>
              </div>
              <div style="font-size: 1.15rem; font-weight: 800; color: #C084FC; font-family: 'JetBrains Mono', monospace;">
                {fwd_pe_str}
              </div>
              <div style="font-size: 0.68rem; color: #64748B; margin-top: 3px;">
                Price / 1-Yr Forward EPS
              </div>
            </div>
          </div>

          <!-- 4. TTM P/E -->
          <div class="col-lg-3 col-sm-6" style="padding: 6px 8px;">
            <div style="background: #090D15; border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 8px; padding: 12px 14px; height: 100%;">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                <span style="font-size: 0.7rem; color: #94A3B8; text-transform: uppercase; font-weight: 700; letter-spacing: 0.04em;">TTM P/E</span>
                <i class="fas fa-history" style="color: #FACC15; opacity: 0.85; font-size: 0.85rem;"></i>
              </div>
              <div style="font-size: 1.15rem; font-weight: 800; color: #FACC15; font-family: 'JetBrains Mono', monospace;">
                {ttm_pe_str}
              </div>
              <div style="font-size: 0.68rem; color: #64748B; margin-top: 3px;">
                Price / Trailing 12M EPS
              </div>
            </div>
          </div>
        </div>

        <!-- 4. Analyst Target Prices Corridor Breakdown -->
        <div style="margin-top: 14px; padding-top: 14px; border-top: 1px solid rgba(255, 255, 255, 0.06);">
          <div style="font-size: 0.7rem; color: #94A3B8; text-transform: uppercase; font-weight: 700; letter-spacing: 0.04em; margin-bottom: 8px;">
            <i class="fas fa-arrows-alt-h mr-1" style="color: #38BDF8;"></i> Analyst Target Price Distribution (12-Month Horizon)
          </div>
          <div style="display: flex; flex-wrap: wrap; gap: 10px;">
            <!-- Low -->
            <div style="flex: 1; min-width: 140px; background: #090D15; padding: 10px 14px; border-radius: 8px; border-left: 3px solid #F87171;">
              <div style="font-size: 0.68rem; color: #94A3B8; font-weight: 600; text-transform: uppercase;">Target Low</div>
              <div style="font-size: 0.95rem; font-weight: 700; color: #F87171; font-family: 'JetBrains Mono', monospace; margin: 2px 0;">{t_low_str}</div>
              <div style="font-size: 0.68rem; color: #64748B;">Bearish Floor</div>
            </div>
            <!-- Median -->
            <div style="flex: 1; min-width: 140px; background: #090D15; padding: 10px 14px; border-radius: 8px; border-left: 3px solid #38BDF8;">
              <div style="font-size: 0.68rem; color: #94A3B8; font-weight: 600; text-transform: uppercase;">Target Median</div>
              <div style="font-size: 0.95rem; font-weight: 700; color: #38BDF8; font-family: 'JetBrains Mono', monospace; margin: 2px 0;">{t_median_str}</div>
              <div style="font-size: 0.68rem; color: #64748B;">Median Target</div>
            </div>
            <!-- Mean -->
            <div style="flex: 1; min-width: 140px; background: #090D15; padding: 10px 14px; border-radius: 8px; border-left: 3px solid #FACC15;">
              <div style="font-size: 0.68rem; color: #94A3B8; font-weight: 600; text-transform: uppercase;">Target Mean</div>
              <div style="font-size: 0.95rem; font-weight: 700; color: #FACC15; font-family: 'JetBrains Mono', monospace; margin: 2px 0;">{t_mean_str}</div>
              <div style="font-size: 0.68rem; color: #64748B;">Consensus Average</div>
            </div>
            <!-- High -->
            <div style="flex: 1; min-width: 140px; background: #090D15; padding: 10px 14px; border-radius: 8px; border-left: 3px solid #34D399;">
              <div style="font-size: 0.68rem; color: #94A3B8; font-weight: 600; text-transform: uppercase;">Target High</div>
              <div style="font-size: 0.95rem; font-weight: 700; color: #34D399; font-family: 'JetBrains Mono', monospace; margin: 2px 0;">{t_high_str}</div>
              <div style="font-size: 0.68rem; color: #64748B;">Bullish Ceiling</div>
            </div>
          </div>
        </div>
      </div>
    </div>
    '''
    return html


def get_similar_stock(port_df):
    if port_df is None or port_df.empty or port_df.shape[0] < 2 or port_df.shape[1] < 2:
        return pd.DataFrame(columns=["stock", "dist"])

    mini_df = port_df
    mini_ret_df = np.log(mini_df / mini_df.shift(1))
    if len(mini_ret_df.index) > 0:
        mini_ret_df = mini_ret_df.drop(mini_ret_df.index[0])

    if mini_ret_df.empty or mini_ret_df.shape[1] < 2:
        return pd.DataFrame(columns=["stock", "dist"])

    sel_stock_df = mini_ret_df[mini_ret_df.columns[0]]
    stock_univ_df = mini_ret_df.drop([mini_ret_df.columns[0]], axis=1)
    similar_df = pd.DataFrame(columns=["stock", "dist"])

    for count in range(0, stock_univ_df.shape[1]):
        stock = stock_univ_df.columns[count]
        distance = math.sqrt(sum((sel_stock_df - stock_univ_df[stock]) ** 2))
        similar_df.loc[count] = [stock, distance]

    similar_df = similar_df.sort_values(axis=0, by=["dist"])
    return similar_df


def get_beta_port(port_df):
    if port_df is None or port_df.empty or port_df.shape[0] < 2:
        return pd.DataFrame(), [], pd.DataFrame(), pd.DataFrame()

    mini_df = port_df
    mini_ret_df = np.log(mini_df / mini_df.shift(1))
    cov_mtx = mini_ret_df.cov()
    corr_mtx = mini_ret_df.corr()
    if cov_mtx.empty or cov_mtx.shape[0] == 0 or cov_mtx.iloc[0, 0] == 0:
        beta_list = [0] * max(0, port_df.shape[1] - 1)
    else:
        beta_series = cov_mtx.iloc[0] / cov_mtx.iloc[0, 0]
        beta_list = beta_series.tolist()[1:]

    return (cov_mtx, beta_list, corr_mtx, mini_ret_df)


def short_name(long_name):
    if long_name == "index" or long_name == "port":
        return long_name
    try:
        coname = str(ia_sinfo.stock_name_code_map[long_name][2]).split()
        if len(coname) > 1:
            coname = coname[0] + " " + coname[1]
        else:
            coname = coname[0]
        return coname[0:min(len(coname), 15)]
    except Exception:
        return str(long_name)[0:15]


def change_headers(port_df):
    renamed_df = port_df.copy()
    col_names = renamed_df.columns.tolist()
    new_names = []
    for cname in col_names:
        new_names.append(short_name(cname))

    renamed_df.columns = new_names
    return renamed_df


def get_kmean_cluster(pret_df, ncluster):
    if pret_df is None or pret_df.empty or pret_df.shape[1] <= 1:
        return [], np.zeros((0, 2)), []

    try:
        pret_df.to_excel(ia_sinfo.log_writer, sheet_name="kmean_pret")
        ia_sinfo.log_writer.save()
    except Exception:
        pass

    pret_Tdf = pret_df.transpose()
    if len(pret_Tdf.index) > 0:
        pret_Tdf = pret_Tdf.drop([pret_Tdf.index[0]])
    cols = list(range(1, pret_Tdf.shape[1]))
    if len(cols) == 0:
        return [], np.zeros((0, 2)), []
    x = pret_Tdf.iloc[:, cols].fillna(0)

    try:
        x.to_excel(ia_sinfo.log_writer, sheet_name="kmean_x")
        ia_sinfo.log_writer.save()
    except Exception:
        pass

    actual_clusters = min(ncluster, max(1, x.shape[0]))
    kmeans5 = KMeans(n_clusters=actual_clusters)
    cluster_list = kmeans5.fit_predict(x)
    nlist = []
    for elem in cluster_list:
        nlist.append("Cluster :" + str(elem + 1))

    perplexity_val = min(50, max(1, x.shape[0] - 1))
    tsne = TSNE(n_components=2, verbose=0, perplexity=perplexity_val, max_iter=500)
    try:
        tsne_results = tsne.fit_transform(x)
    except Exception:
        tsne_results = np.zeros((x.shape[0], 2))

    return nlist, tsne_results, cluster_list


def unique_groups(co_score_df, factor):
    unique_group = {}
    if co_score_df is None or co_score_df.empty:
        return unique_group, []

    companies = co_score_df.index.tolist()
    count = len(companies)
    if count == 0:
        return unique_group, []

    max_score = co_score_df.iloc[0][co_score_df.columns[0]]
    if pd.isna(max_score) or max_score == 0:
        max_score = 1

    grp_count = 0
    for row in range(0, count):
        ridx = co_score_df.index[row]
        for col in range(row, count):
            colname = co_score_df.columns[col]
            score = co_score_df.loc[ridx][colname]
            if score > max_score * factor:
                existing = 0
                for grp in list(unique_group.keys()):
                    if colname in unique_group[grp]:
                        existing = 1
                        if ridx == colname:
                            grp_count += 1
                        break
                if existing == 1:
                    continue

                if ridx != colname:
                    try:
                        unique_group[grp_count].append(colname)
                    except Exception:
                        unique_group[grp_count] = [colname]
                else:
                    grp_count += 1
                    unique_group[grp_count] = [colname]

    ug2 = {}
    count = 0
    for grp in list(unique_group.keys()):
        count += 1
        ug2[count] = unique_group[grp]

    unique_group = ug2

    unique_list = []
    for co in companies:
        found = False
        for grp in list(unique_group.keys()):
            if co in unique_group[grp]:
                unique_list.append("Group : " + str(int(grp)))
                found = True
                break
        if not found:
            unique_list.append("Group : 1")

    return unique_group, unique_list


def create_groups(clust_iter_df):
    if clust_iter_df is None or clust_iter_df.empty:
        return []

    companies = clust_iter_df.index.tolist()
    iter_count = clust_iter_df.shape[1]
    co_score_df = pd.DataFrame(index=companies, columns=companies)
    for co in companies:
        for co2 in companies:
            score = 0
            for ic in range(0, iter_count):
                colname = "iter " + str(int(ic))
                if colname in clust_iter_df.columns and (clust_iter_df.loc[co][colname] == clust_iter_df.loc[co2][colname]):
                    score += 1
            co_score_df.loc[co][co2] = score

    try:
        co_score_df.to_excel(ia_sinfo.log_writer, sheet_name="co_score_df")
        ia_sinfo.log_writer.save()
    except Exception:
        pass

    ug, clist = unique_groups(co_score_df, 0.69)

    max_len = 0
    for grp in list(ug.keys()):
        if len(ug[grp]) > max_len:
            max_len = len(ug[grp])

    for grp in list(ug.keys()):
        if len(ug[grp]) < max_len:
            for ct in range(len(ug[grp]), max_len):
                ug[grp].append("NA")

    try:
        tdf = pd.DataFrame(ug)
        tdf.to_excel(ia_sinfo.log_writer, sheet_name="iter_cluster")
        ia_sinfo.log_writer.save()
    except Exception:
        pass

    return clist


def iterate_clusters(pret_df, no_clusters, no_iteration):
    if pret_df is None or pret_df.empty or pret_df.shape[1] <= 1:
        return pd.DataFrame(), []

    temp_list = pret_df.columns.tolist()
    clust_df = pd.DataFrame(index=temp_list[1:])

    for iter in range(0, no_iteration):
        cluster_list, pca_result, num_clist = get_kmean_cluster(pret_df, no_clusters)
        if len(num_clist) == len(clust_df.index):
            clust_df["iter " + str(int(iter))] = num_clist

    try:
        clust_df.to_excel(ia_sinfo.log_writer, sheet_name="cluster_iter")
        ia_sinfo.log_writer.save()
    except Exception:
        pass

    clust_norm_list = create_groups(clust_df)

    return clust_df, clust_norm_list


def ia_go_treeplot(port_df, title):
    if port_df is None or port_df.empty or port_df.shape[0] < 2 or port_df.shape[1] < 2:
        fig = go.Figure()
        fig.update_layout(title=title + " (Insufficient Data)", paper_bgcolor="#0D131F", font=dict(color="#94A3B8"))
        empty_div = plot(fig, output_type='div')
        return (empty_div, empty_div, empty_div)

    port_df = change_headers(port_df)
    cov_df, beta_list, corr_df, pret_df = get_beta_port(port_df)
    port_df = port_df.drop([port_df.columns[0]], axis=1)

    if port_df.empty or len(port_df.columns) == 0:
        fig = go.Figure()
        fig.update_layout(title=title + " (Insufficient Data)", paper_bgcolor="#0D131F", font=dict(color="#94A3B8"))
        empty_div = plot(fig, output_type='div')
        return (empty_div, empty_div, empty_div)

    st_series = port_df.iloc[0]
    en_series = port_df.iloc[-1]
    mini_df = pd.DataFrame(columns=["stock", "start", "end", "beta"], index=st_series.index.tolist())
    mini_df["stock"] = st_series.index.tolist()
    mini_df["start"] = st_series.values.tolist()
    mini_df["end"] = en_series.values.tolist()
    mini_df["gain"] = round((mini_df["end"] / mini_df["start"].replace(0, np.nan) - 1) * 100, 1).fillna(0)
    mini_df["gain"] = [str(elem) + " %" for elem in mini_df["gain"].values.tolist()]
    mini_df["beta"] = beta_list if len(beta_list) == len(mini_df) else [0] * len(mini_df)
    cluster_list, pca_result, num_clist = get_kmean_cluster(pret_df, min(7, max(1, len(st_series))))
    cl_iter_df, cl_iter_list = iterate_clusters(pret_df, min(5, max(1, len(st_series))), 29)
    mini_df["sector"] = cl_iter_list if len(cl_iter_list) == len(mini_df) else ["Sector 1"] * len(mini_df)

    ht = 600

    pca_df = pd.DataFrame(pca_result if len(pca_result) == len(st_series) else np.zeros((len(st_series), 2)), columns=["dim1", "dim2"])
    pca_df["stock"] = st_series.index.tolist()
    pca_df["sector"] = cluster_list if len(cluster_list) == len(pca_df) else ["Cluster 1"] * len(pca_df)
    pca_df["size"] = en_series.values.tolist()
    pca_df["size"] = pca_df["size"].fillna(1.0)

    fig_scat = px.scatter(pca_df, x="dim1", y="dim2", size="size", color="sector", hover_name="stock")
    fig_scat.update_layout(autosize=True, height=ht, paper_bgcolor="#0D131F", plot_bgcolor="#090D15", font=dict(color="#F8FAFC"))

    fig = px.treemap(mini_df, path=["sector", "stock", "gain"], values="end", color="beta",
                     color_continuous_scale='RdBu_r')
    fig.update_layout(autosize=True, height=ht, paper_bgcolor="#0D131F", font=dict(color="#F8FAFC"))

    if not corr_df.empty:
        corr_df["cmean"] = corr_df.mean(axis=1)
        rmean = corr_df.mean(axis=0)
        corr_df.loc["rmean"] = rmean.values.tolist()
        corr_df = corr_df.sort_values(axis=0, by=["cmean"])
        corr_df = corr_df.sort_values(axis=1, by=["rmean"])
        fig_corr = go.Figure()
        fig_corr.add_trace(go.Heatmap(z=corr_df.values, x=corr_df.index.values, y=corr_df.columns.values, colorscale='Viridis'))
        fig_corr.update_layout(autosize=True, height=max(400, corr_df.shape[0] * 32), paper_bgcolor="#0D131F", font=dict(color="#F8FAFC"))
    else:
        fig_corr = go.Figure()

    return (plot(fig, output_type='div'), plot(fig_corr, output_type='div'), plot(fig_scat, output_type='div'))


def ia_go_graph(prices_df, mode, m2, y_scale, title, pe_data=None):
    if prices_df is None or prices_df.empty or len(prices_df.columns) == 0 or len(prices_df) == 0:
        fig = go.Figure()
        fig.update_layout(title=title + " (No Data Available)", paper_bgcolor="#0D131F", font=dict(color="#94A3B8"))
        return plot(fig, output_type='div')

    has_phase = (len(prices_df.columns) > 1 and prices_df.columns[-1] == 'Phase')
    price_cols = prices_df.columns[0:-1] if has_phase else prices_df.columns
    eval_cols = [c for c in price_cols if not str(c).startswith("RelVal ")]

    try:
        mx = 100
        mn = 1
        if len(eval_cols) > 0:
            first_series = prices_df[eval_cols[0]].dropna()
            if len(first_series) > 0:
                mx = np.nanmax(first_series)
                mn = np.nanmin(first_series)
            for col in eval_cols[1:]:
                col_series = prices_df[col].dropna()
                if len(col_series) > 0:
                    mx = max(np.nanmax(col_series), mx)
                    mn = min(np.nanmin(col_series), mn)
    except Exception:
        mx = 100
        mn = 1

    if np.isnan(mx) or mx <= 0:
        mx = 100
    if np.isnan(mn) or mn <= 0:
        mn = 1

    has_pe = (pe_data is not None and isinstance(pe_data, dict) and 'daily_pe' in pe_data and pe_data['daily_pe'] is not None and not pe_data['daily_pe'].empty)
    has_secondary = (m2 == 1 or m2 == 0)
    has_peg = (m2 == 'b' and has_pe and 'daily_peg_plot' in pe_data and pe_data['daily_peg_plot'] is not None and not pe_data['daily_peg_plot'].dropna().empty)

    if has_pe:
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.04,
            row_heights=[0.60, 0.40] if has_peg else [0.65, 0.35],
            specs=[[{"secondary_y": has_secondary}], [{"secondary_y": has_peg}]]
        )
    else:
        fig = go.Figure()

    def _add_primary_trace(trace):
        if has_pe:
            fig.add_trace(trace, row=1, col=1, secondary_y=False)
        else:
            fig.add_trace(trace)

    def _add_relval_trace(trace):
        if has_pe:
            fig.add_trace(trace, row=1, col=1, secondary_y=True)
        else:
            trace.yaxis = "y2"
            fig.add_trace(trace)

    # Contrast shading during bear/recession cycles (soft translucent rose for contrast)
    if mode == 1 and has_phase:
        _add_primary_trace(go.Scatter(
            x=prices_df.index,
            y=(round(mx * 1.05, 0)) * prices_df['Phase'],
            line=dict(color='rgba(244, 63, 94, 0.28)', width=1, dash='dot'),
            fill='tozeroy',
            fillcolor='rgba(244, 63, 94, 0.12)',
            mode='lines',
            name='Bear Phase / Downturn',
            showlegend=(m2 == 1 or m2 == 0)
        ))

    COLOR_BENCHMARK = "#38BDF8"  # Electric Sky Blue for Market Index
    COLOR_STOCK = "#FACC15"      # Radiant Yellow for Stock Price
    COLOR_RELVAL = "#FB923C"     # Vivid Warm Tangerine / Coral Orange for Relative Value (distinct from TTM P/E)
    COLOR_PE = "#C084FC"         # Vibrant Soft Violet for TTM P/E
    palette = ["#0E8CE4", "#10B981", "#38BDF8", "#F59E0B", "#A855F7", "#EC4899", "#E2E8F0"]

    if m2 == 1:
        rel_cols = [c for c in price_cols if str(c).startswith("RelVal ")]
        asset_cols = [c for c in price_cols if not str(c).startswith("RelVal ")]

        # Relative performance across cycles: consistent Blue for Market, Yellow for Stock
        for ctr, col in enumerate(asset_cols):
            is_mkt = (ctr % 2 == 0)
            cur_color = COLOR_BENCHMARK if is_mkt else COLOR_STOCK
            group_name = "Market Index" if is_mkt else "Stock Price"
            base_col = col.rsplit(' ', 1)[0] if ' ' in str(col) else str(col)
            cycle_idx = col.rsplit(' ', 1)[1] if ' ' in str(col) else str(ctr // 2)
            display_name = short_name(base_col)

            col_series = prices_df[col].dropna()
            if col_series.empty:
                continue

            n_pts = len(col_series)
            marker_sizes = [0] * (n_pts - 1) + [8] if n_pts > 1 else [8]
            marker_widths = [0] * (n_pts - 1) + [1.8] if n_pts > 1 else [1.8]

            _add_primary_trace(go.Scatter(
                x=col_series.index,
                y=col_series.values,
                line=dict(color=cur_color, width=2.2),
                mode='lines+markers',
                marker=dict(
                    size=marker_sizes,
                    color=cur_color,
                    symbol='circle',
                    line=dict(width=marker_widths, color='#FFFFFF')
                ),
                name=display_name,
                legendgroup=group_name,
                showlegend=(ctr < 2),
                hovertemplate=f"<b>{display_name}</b> (Period {cycle_idx})<br>Date: %{{x|%d %b %Y}}<br>Indexed: %{{y:.2f}}<extra></extra>"
            ))

        # Relative Value: Stock / Market Index ratio (disabled by default, enabled on click)
        for r_idx, col in enumerate(rel_cols):
            cycle_idx = col.rsplit(' ', 1)[1] if ' ' in str(col) else str(r_idx)
            col_series = prices_df[col].dropna()
            if col_series.empty:
                continue

            n_pts = len(col_series)
            marker_sizes = [0] * (n_pts - 1) + [8] if n_pts > 1 else [8]
            marker_widths = [0] * (n_pts - 1) + [1.8] if n_pts > 1 else [1.8]

            _add_relval_trace(go.Scatter(
                x=col_series.index,
                y=col_series.values,
                line=dict(color=COLOR_RELVAL, width=2.2),
                mode='lines+markers',
                marker=dict(
                    size=marker_sizes,
                    color=COLOR_RELVAL,
                    symbol='circle',
                    line=dict(width=marker_widths, color='#FFFFFF')
                ),
                name="Relative Value (Stock / Market)",
                legendgroup="Relative Value",
                showlegend=(r_idx == 0),
                visible="legendonly",
                hovertemplate=f"<b>Relative Value (Stock / Market)</b> (Period {cycle_idx})<br>Date: %{{x|%d %b %Y}}<br>Ratio: %{{y:.2f}}<extra></extra>"
            ))
    elif m2 == "r":
        for col in price_cols:
            display_name = short_name(col)
            col_series = prices_df[col].dropna()
            if col_series.empty:
                continue

            n_pts = len(col_series)
            marker_sizes = [0] * (n_pts - 1) + [8] if n_pts > 1 else [8]
            marker_widths = [0] * (n_pts - 1) + [1.8] if n_pts > 1 else [1.8]

            _add_primary_trace(go.Scatter(
                x=col_series.index,
                y=col_series.values,
                line=dict(color=COLOR_BENCHMARK, width=2.2),
                mode='lines+markers',
                marker=dict(
                    size=marker_sizes,
                    color=COLOR_BENCHMARK,
                    symbol='circle',
                    line=dict(width=marker_widths, color='#FFFFFF')
                ),
                name=display_name,
                hovertemplate=f"<b>{display_name}</b><br>Date: %{{x|%d %b %Y}}<br>Price: %{{y:.2f}}<extra></extra>"
            ))
    elif m2 == "b":
        for col in price_cols:
            display_name = short_name(col)
            col_series = prices_df[col].dropna()
            if col_series.empty:
                continue

            n_pts = len(col_series)
            marker_sizes = [0] * (n_pts - 1) + [8] if n_pts > 1 else [8]
            marker_widths = [0] * (n_pts - 1) + [1.8] if n_pts > 1 else [1.8]

            _add_primary_trace(go.Scatter(
                x=col_series.index,
                y=col_series.values,
                line=dict(color=COLOR_STOCK, width=2.2),
                mode='lines+markers',
                marker=dict(
                    size=marker_sizes,
                    color=COLOR_STOCK,
                    symbol='circle',
                    line=dict(width=marker_widths, color='#FFFFFF')
                ),
                name=display_name,
                hovertemplate=f"<b>{display_name}</b><br>Date: %{{x|%d %b %Y}}<br>Price: %{{y:.2f}}<extra></extra>"
            ))
    elif m2 == 0:
        for ctr, col in enumerate(price_cols):
            cur_color = COLOR_BENCHMARK if ctr == 0 else COLOR_STOCK
            display_name = short_name(col)
            col_series = prices_df[col].dropna()
            if col_series.empty:
                continue

            n_pts = len(col_series)
            marker_sizes = [0] * (n_pts - 1) + [8] if n_pts > 1 else [8]
            marker_widths = [0] * (n_pts - 1) + [1.8] if n_pts > 1 else [1.8]

            _add_primary_trace(go.Scatter(
                x=col_series.index,
                y=col_series.values,
                line=dict(color=cur_color, width=2.2),
                mode='lines+markers',
                marker=dict(
                    size=marker_sizes,
                    color=cur_color,
                    symbol='circle',
                    line=dict(width=marker_widths, color='#FFFFFF')
                ),
                name=display_name,
                hovertemplate=f"<b>{display_name}</b><br>Date: %{{x|%d %b %Y}}<br>Indexed: %{{y:.2f}}<extra></extra>"
            ))
        if len(price_cols) >= 2:
            rel_series = (prices_df[price_cols[1]] / prices_df[price_cols[0]].replace(0, np.nan)).dropna()
            if not rel_series.empty:
                n_pts = len(rel_series)
                marker_sizes = [0] * (n_pts - 1) + [8] if n_pts > 1 else [8]
                marker_widths = [0] * (n_pts - 1) + [1.8] if n_pts > 1 else [1.8]

                _add_relval_trace(go.Scatter(
                    x=rel_series.index,
                    y=rel_series.values,
                    line=dict(color=COLOR_RELVAL, width=2.2),
                    mode='lines+markers',
                    marker=dict(
                        size=marker_sizes,
                        color=COLOR_RELVAL,
                        symbol='circle',
                        line=dict(width=marker_widths, color='#FFFFFF')
                    ),
                    name="Relative Value (Stock / Market)",
                    visible="legendonly",
                    hovertemplate=f"<b>Relative Value (Stock / Market)</b><br>Date: %{{x|%d %b %Y}}<br>Ratio: %{{y:.2f}}<extra></extra>"
                ))
    else:
        for ctr, col in enumerate(price_cols):
            cur_color = COLOR_BENCHMARK if ctr == 0 else (COLOR_STOCK if ctr == 1 else palette[ctr % len(palette)])
            display_name = short_name(col)
            col_series = prices_df[col].dropna()
            if col_series.empty:
                continue

            n_pts = len(col_series)
            marker_sizes = [0] * (n_pts - 1) + [8] if n_pts > 1 else [8]
            marker_widths = [0] * (n_pts - 1) + [1.8] if n_pts > 1 else [1.8]

            _add_primary_trace(go.Scatter(
                x=col_series.index,
                y=col_series.values,
                line=dict(color=cur_color, width=2.2),
                mode='lines+markers',
                marker=dict(
                    size=marker_sizes,
                    color=cur_color,
                    symbol='circle',
                    line=dict(width=marker_widths, color='#FFFFFF')
                ),
                name=display_name,
                hovertemplate=f"<b>{display_name}</b><br>Date: %{{x|%d %b %Y}}<br>Value: %{{y:.2f}}<extra></extra>"
            ))

    # Row 2 Valuation Corridor Traces (Alternative 2: Median PE & +-1 SD Corridor)
    if has_pe:
        daily_pe = pe_data["daily_pe"].copy()
        target_idx = prices_df.index
        if target_idx.tz is not None:
            if daily_pe.index.tz is None:
                try:
                    daily_pe.index = daily_pe.index.tz_localize(target_idx.tz)
                except Exception:
                    daily_pe.index = pd.to_datetime(daily_pe.index).tz_localize(target_idx.tz)
            else:
                daily_pe.index = daily_pe.index.tz_convert(target_idx.tz)
        else:
            if daily_pe.index.tz is not None:
                daily_pe.index = daily_pe.index.tz_localize(None)

        pe_series = daily_pe.reindex(target_idx, method='ffill').bfill().dropna()
        if not pe_series.empty:
            med_pe = pe_data["median_pe"]
            up_pe = pe_data["upper_pe"]
            lo_pe = pe_data["lower_pe"]

            # +1 SD Overvalued Band
            fig.add_trace(go.Scatter(
                x=pe_series.index,
                y=[up_pe] * len(pe_series),
                line=dict(color="rgba(244, 63, 94, 0.45)", width=1, dash="dash"),
                mode="lines",
                name="+1 SD (Overvalued Band)",
                showlegend=False,
                hoverinfo="skip"
            ), row=2, col=1, secondary_y=False if has_peg else None)

            # -1 SD Undervalued Band with corridor fill
            fig.add_trace(go.Scatter(
                x=pe_series.index,
                y=[lo_pe] * len(pe_series),
                line=dict(color="rgba(52, 211, 153, 0.45)", width=1, dash="dash"),
                fill='tonexty',
                fillcolor='rgba(56, 189, 248, 0.05)',
                mode="lines",
                name="-1 SD (Undervalued Band)",
                showlegend=False,
                hoverinfo="skip"
            ), row=2, col=1, secondary_y=False if has_peg else None)

            # Historical Median PE
            fig.add_trace(go.Scatter(
                x=pe_series.index,
                y=[med_pe] * len(pe_series),
                line=dict(color="#94A3B8", width=1.5, dash="dot"),
                mode="lines",
                name=f"Median P/E ({med_pe:.1f}x)",
                showlegend=False,
                hovertemplate=f"<b>Historical Median P/E</b>: {med_pe:.1f}x<extra></extra>"
            ), row=2, col=1, secondary_y=False if has_peg else None)

            # TTM P/E Ratio line
            n_pe = len(pe_series)
            pe_marker_sizes = [0] * (n_pe - 1) + [8] if n_pe > 1 else [8]
            pe_marker_widths = [0] * (n_pe - 1) + [1.8] if n_pe > 1 else [1.8]

            fig.add_trace(go.Scatter(
                x=pe_series.index,
                y=pe_series.values,
                line=dict(color=COLOR_PE, width=2.2),
                mode="lines+markers",
                marker=dict(
                    size=pe_marker_sizes,
                    color=COLOR_PE,
                    symbol='circle',
                    line=dict(width=pe_marker_widths, color='#FFFFFF')
                ),
                name="TTM P/E Ratio",
                hovertemplate="<b>TTM P/E</b>: %{y:.1f}x<br>Date: %{x|%d %b %Y}<extra></extra>"
            ), row=2, col=1, secondary_y=False if has_peg else None)

            # TTM PEG Ratio (Dual-Axis Sub-chart in Row 2)
            if has_peg:
                daily_peg_plot = pe_data["daily_peg_plot"].copy()
                if target_idx.tz is not None:
                    if daily_peg_plot.index.tz is None:
                        try:
                            daily_peg_plot.index = daily_peg_plot.index.tz_localize(target_idx.tz)
                        except Exception:
                            daily_peg_plot.index = pd.to_datetime(daily_peg_plot.index).tz_localize(target_idx.tz)
                    else:
                        daily_peg_plot.index = daily_peg_plot.index.tz_convert(target_idx.tz)
                else:
                    if daily_peg_plot.index.tz is not None:
                        daily_peg_plot.index = daily_peg_plot.index.tz_localize(None)

                peg_series = daily_peg_plot.reindex(target_idx, method='ffill').dropna()
                if not peg_series.empty:
                    # Benchmark PEG = 1.0 (Fair Value) reference line
                    fig.add_trace(go.Scatter(
                        x=peg_series.index,
                        y=[1.0] * len(peg_series),
                        line=dict(color="rgba(45, 212, 191, 0.45)", width=1.2, dash="dash"),
                        mode="lines",
                        name="PEG = 1.0 (Fair Value)",
                        showlegend=False,
                        hoverinfo="skip"
                    ), row=2, col=1, secondary_y=True)

                    # Median TTM PEG reference line
                    med_peg = pe_data.get("median_peg")
                    if med_peg is None and not peg_series.empty:
                        med_peg = float(peg_series.median())

                    if med_peg is not None and not np.isnan(med_peg):
                        fig.add_trace(go.Scatter(
                            x=peg_series.index,
                            y=[med_peg] * len(peg_series),
                            line=dict(color="#5EEAD4", width=1.5, dash="dot"),
                            mode="lines",
                            name=f"Median TTM PEG ({med_peg:.2f}x)",
                            showlegend=False,
                            hovertemplate=f"<b>Median TTM PEG</b>: {med_peg:.2f}x<extra></extra>"
                        ), row=2, col=1, secondary_y=True)

                    # Daily TTM PEG line
                    n_peg = len(peg_series)
                    peg_marker_sizes = [0] * (n_peg - 1) + [8] if n_peg > 1 else [8]
                    peg_marker_widths = [0] * (n_peg - 1) + [1.8] if n_peg > 1 else [1.8]

                    fig.add_trace(go.Scatter(
                        x=peg_series.index,
                        y=peg_series.values,
                        line=dict(color="#2DD4BF", width=2.0),
                        mode="lines+markers",
                        marker=dict(
                            size=peg_marker_sizes,
                            color="#2DD4BF",
                            symbol='circle',
                            line=dict(width=peg_marker_widths, color='#FFFFFF')
                        ),
                        name="TTM PEG Ratio",
                        hovertemplate="<b>TTM PEG</b>: %{y:.2f}x<br>Date: %{x|%d %b %Y}<extra></extra>"
                    ), row=2, col=1, secondary_y=True)

    try:
        if y_scale == "log":
            low_r = math.log(max(0.01, round(mn * .95, 2)), 10)
            high_r = math.log(max(0.02, round(mx * 1.05, 2)), 10)
            y_range = [low_r, high_r]
        else:
            y_range = [round(mn * .95, 2), round(mx * 1.05, 2)]
    except Exception:
        y_range = None

    if has_pe:
        fig.update_layout(
            autosize=True,
            height=580,
            paper_bgcolor="#0D131F",
            plot_bgcolor="#090D15",
            font=dict(color="#F8FAFC", family="Plus Jakarta Sans, sans-serif"),
            title=dict(text=title, font=dict(color="#F8FAFC", size=13), x=0.01, y=0.98),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                font=dict(color="#94A3B8", size=10, family="JetBrains Mono, monospace")
            ),
            margin=dict(l=35, r=40, t=65, b=35),
            hovermode="x unified"
        )
        y1_cfg = dict(mirror=True, type=y_scale, gridcolor="rgba(30, 41, 59, 0.7)", zerolinecolor="#1E293B")
        if y_range is not None:
            y1_cfg["range"] = y_range
        fig.update_yaxes(y1_cfg, row=1, col=1, secondary_y=False)

        if has_secondary:
            fig.update_yaxes(
                title=dict(text="Relative Value (Ratio)", font=dict(color=COLOR_RELVAL, size=11, family="Plus Jakarta Sans, sans-serif")),
                showgrid=False,
                zeroline=False,
                type="linear",
                rangemode="nonnegative",
                tickfont=dict(color=COLOR_RELVAL, size=10, family="JetBrains Mono, monospace"),
                row=1, col=1, secondary_y=True
            )

        if has_peg:
            fig.update_yaxes(
                title=dict(text="TTM P/E", font=dict(color=COLOR_PE, size=11, family="Plus Jakarta Sans, sans-serif")),
                mirror=True,
                gridcolor="rgba(30, 41, 59, 0.7)",
                zerolinecolor="#1E293B",
                tickfont=dict(color=COLOR_PE, size=10, family="JetBrains Mono, monospace"),
                row=2, col=1, secondary_y=False
            )
            fig.update_yaxes(
                title=dict(text="TTM PEG", font=dict(color="#2DD4BF", size=11, family="Plus Jakarta Sans, sans-serif")),
                showgrid=False,
                zeroline=False,
                type="linear",
                rangemode="nonnegative",
                tickfont=dict(color="#2DD4BF", size=10, family="JetBrains Mono, monospace"),
                row=2, col=1, secondary_y=True
            )
        else:
            fig.update_yaxes(
                title=dict(text="TTM P/E", font=dict(color=COLOR_PE, size=11, family="Plus Jakarta Sans, sans-serif")),
                mirror=True,
                gridcolor="rgba(30, 41, 59, 0.7)",
                zerolinecolor="#1E293B",
                tickfont=dict(color=COLOR_PE, size=10, family="JetBrains Mono, monospace"),
                row=2, col=1
            )
        fig.update_xaxes(mirror=True, gridcolor="rgba(30, 41, 59, 0.7)", zerolinecolor="#1E293B", showticklabels=False, row=1, col=1)
        fig.update_xaxes(mirror=True, gridcolor="rgba(30, 41, 59, 0.7)", zerolinecolor="#1E293B", row=2, col=1)

    else:
        yaxis_cfg = dict(
            mirror=True,
            type=y_scale,
            gridcolor="rgba(30, 41, 59, 0.7)",
            zerolinecolor="#1E293B"
        )
        if y_range is not None:
            yaxis_cfg["range"] = y_range

        fig.update_layout(
            autosize=True,
            height=500,
            paper_bgcolor="#0D131F",
            plot_bgcolor="#090D15",
            font=dict(color="#F8FAFC", family="Plus Jakarta Sans, sans-serif"),
            title=dict(text=title, font=dict(color="#F8FAFC", size=13), x=0.01, y=0.98),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                font=dict(color="#94A3B8", size=11, family="JetBrains Mono, monospace")
            ),
            margin=dict(l=30, r=40, t=65, b=35),
            yaxis=yaxis_cfg,
            yaxis2=dict(
                title=dict(text="Relative Value (Ratio)", font=dict(color=COLOR_RELVAL, size=11, family="Plus Jakarta Sans, sans-serif")),
                overlaying="y",
                side="right",
                type="linear",
                rangemode="nonnegative",
                showgrid=False,
                zeroline=False,
                tickfont=dict(color=COLOR_RELVAL, size=10, family="JetBrains Mono, monospace")
            )
        )
        fig.update_xaxes(mirror=True, gridcolor="rgba(30, 41, 59, 0.7)", zerolinecolor="#1E293B")

    return plot(fig, output_type='div')


def ia_st2tk(stock_list):
    master_dict = {"NIFTY50": "^NSEI",
                   "SENSEX": "^BSESN",

                   "AJANTA PHARMA": "AJANTPHARM.NS",
                   "ASIAN PAINTS": "ASIANPAINT.NS",
                   "BANDHAN BK": "BANDHANBNK.NS",
                   "BLUEDART": "BLUEDART.NS",
                   "CADILA HEALTH": "CADILAHC.NS",
                   "CASTROL IND": "CASTROLIND.NS",
                   "CRISIL": "CRISIL.NS",
                   "DIVIS LAB": "DIVISLAB.NS",
                   "DR LAL PATH": "LALPATHLAB.NS",
                   "EICHER MOT": "EICHERMOT.NS",
                   "HCL TECH": "HCLTECH.NS",
                   "HDFC BK": "HDFCBANK.NS",
                   "HDFC LIFE": "HDFCLIFE.NS",
                   "ICICI LOMBARD": "ICICIGI.NS",
                   "INDUSIND BK": "INDUSINDBK.NS",
                   "INFO EDGE": "NAUKRI.NS",
                   "INFOSYS": "INFY.NS",
                   "ITC": "ITC.NS",
                   "JUBI FOOD": "JUBLFOOD.NS",
                   "LT INFOTECH": "LTI.NS",
                   "LIC HOUSING": "LICHSGFIN.NS",
                   "LUPIN": "LUPIN.NS",
                   "MARUTI": "MARUTI.NS",
                   "MOTHERSON": "MOTHERSUMI.NS",
                   "PAGE IND": "PAGEIND.NS",
                   "SHREE CEM": "SHREECEM.NS",
                   "SUN PHARMA": "SUNPHARMA.NS",
                   "TCS": "TCS.NS",
                   "TATA MOT": "TATAMOTORS.NS",
                   "TITAN": "TITAN.NS",
                   "ULTRATECH": "ULTRACEMCO.NS",
                   "UNITED SPIRITS": "MCDOWELL-N.NS",
                   "UTI AMC": "UTIAMC.NS",
                   "VMART": "VMART.NS",

                   }

    ticker_list = []

    for stock in stock_list:

        try:
            ticker_list.append(master_dict[stock])
        except:
            ticker_list.append("ERR: Ticker not found")

    return ticker_list


SL = ["^NSEI", "ITC.NS"]
#SL = ["^NSEI"]
# SL = ["^NSEI", "BANDHANBNK.NS", "ITC.NS"]
stdate = dt.date(2019, 12, 31)
endate = dt.date(2021, 5, 4)

#fname = r"D:\Backup\Rohit\Work\New Technologies\Cookie Can Portfolio\Black Dashboard\black-dashboard-django\Portfolio Template.xlsx"
#ccan_port_df = pd.read_excel(fname, sheet_name="Portfolio", engine="openpyxl")
#ccan_port_df = ccan_port_df.loc[ccan_port_df['company'] != "x"]
#ccan_port_df = ccan_port_df[ccan_port_df['company'].notna()]

#cl_fname = r"D:\Backup\Rohit\Work\New Technologies\Cookie Can Portfolio\Black Dashboard\black-dashboard-django\app\data_monitor.xlsx"
#cluster_df = pd.read_excel(cl_fname, sheet_name="cluster_iter", engine="openpyxl")
#cluster_df.index = cluster_df[cluster_df.columns[0]].tolist()
#cluster_df = cluster_df.drop([cluster_df.columns[0]], axis=1)
#create_groups(cluster_df)
#ia_plot_port_prices(SL, stdate, endate, "log", ccan_port_df)
# ia_plot_similar_stocks(SL,stdate,endate)
# ia_plot_similar_stocks(SL,stdate,endate, "log", ccan_port_df)
# df, ignore1, ignore2 = ia_get_prices(SL,stdate,endate)
#ia_plot_prices(SL, stdate, endate, "log")
# cycles = ia_get_cycle_dates(df, 0.25)
# ia_calc_risk_metrics(df, cycles)

#ia_get_financials("ITC.NS", "bse", stdate, endate)

# pdf = ia_get_prices(SL, stdate, endate,"xxx" )
# list1 = ia_get_cycle_dates(pdf,0.25)
# print(list1)
# https://towardsdatascience.com/visualization-with-plotly-express-comprehensive-guide-eb5ee4b50b57
# https://towardsdatascience.com/visualization-with-plotly-express-comprehensive-guide-eb5ee4b50b57
