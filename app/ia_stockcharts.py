import pandas as pd
import yfinance as yf
import numpy as np
import pandas_datareader as wb
import datetime as dt
from plotly.offline import plot
from plotly.graph_objs import Scatter
import plotly.express as px
import plotly.graph_objects as go
# from . import ia_stock_index_info as ia_stat
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


def ia_plot_prices(stock_list, sdate, edate, y_scale):
    Decline = 0.25

    orig_prices_df, act_sdate, missing_stocks, act_edate = ia_get_prices(stock_list, sdate, edate)

    if orig_prices_df is None or orig_prices_df.empty or orig_prices_df.dropna(how='all').empty or len(orig_prices_df) == 0:
        empty_plot = "<div><h4 style=\"text-align:center; color:orange;\"><b>No stock price data available for the selected dates/tickers.</b></h4></div>"
        empty_tbl = "<div><h4 style=\"text-align:center; color:orange;\"><b>No data available.</b></h4></div>"
        missing_info = ", ".join([f"{k}: {v}" for k, v in missing_stocks.items()]) if missing_stocks else "No data retrieved"
        msg = f"Unable to fetch price data ({missing_info})"
        return (empty_plot, empty_tbl, empty_tbl, empty_plot, empty_plot, empty_plot, msg)

    try:
        prices_df = orig_prices_df.loc[act_sdate:act_edate]
    except Exception:
        prices_df = orig_prices_df

    if prices_df.empty:
        prices_df = orig_prices_df

    norm_prices_df = ia_norm_price(prices_df)
    cycles = ia_get_cycle_dates(prices_df, Decline)

    prices_df = ia_populate_cycle(prices_df, cycles)
    norm_prices_df = ia_populate_cycle(norm_prices_df, cycles)

    pdiv1 = ia_go_graph(prices_df[[prices_df.columns[0], prices_df.columns[-1]]], 1, "r", y_scale, "Benchmark index") if len(prices_df.columns) >= 2 else "<div></div>"
    pdiv2 = ia_go_graph(prices_df[[prices_df.columns[1], prices_df.columns[-1]]], 1, "b", y_scale, "Stock price") if len(prices_df.columns) >= 2 else "<div></div>"
    pdiv3 = ia_go_graph(norm_prices_df, 1, 0, y_scale, "Relative performance over the period")

    norm_reset_df = ia_reset_returns(ia_norm_price(prices_df), cycles)
    norm_reset_df = ia_populate_cycle(norm_reset_df, cycles)

    pdiv4 = ia_go_graph(norm_reset_df, 1, 1, y_scale, "Relative performance across cycles")

    if prices_df is not None and not prices_df.empty and len(prices_df.columns) >= 2 and cycles:
        risk_metric_df = ia_calc_risk_metrics(prices_df[[prices_df.columns[0], prices_df.columns[1]]], cycles)
    else:
        risk_metric_df = pd.DataFrame()

    pdiv5 = ia_go_table(risk_metric_df, "s", "Relative performance & beta across cycles")
    pdiv6 = pdiv5

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

    return (pdiv4, pdiv5, pdiv6, pdiv3, pdiv2, pdiv1, msg)


def ia_get_financials(comp, exch, sdate, edate):
    exchange = exch
    mst = sdate.month // 3
    yst = sdate.year
    if mst == 0:
        yst = yst - 1
        mst = 4
    men = edate.month // 3
    yen = edate.year
    if men == 0:
        yen = yen - 1
        men = 4

    qstart = (yst - 2005 - 1) * 4 + mst + 48
    qend = (yen - 2005 - 1) * 4 + men + 48
    ctkr = comp
    ccode = ia_sinfo.stock_name_code_map[ctkr][0]
    cname = ia_sinfo.stock_name_code_map[ctkr][2]

    try:
        qtr_df = bse_res.exch_get_results(exchange, ccode, cname, qstart, qend, "qtr", ctkr)
    except Exception:
        qtr_df = pd.DataFrame()

    if qtr_df is not None and not qtr_df.empty:
        col_limit = min(12, qtr_df.shape[1])
        df_one = qtr_df[qtr_df.columns[0:col_limit]]
        df_two = qtr_df.drop(axis=1, columns=qtr_df.columns[2:col_limit]) if qtr_df.shape[1] > 2 else pd.DataFrame()
    else:
        df_one = pd.DataFrame()
        df_two = pd.DataFrame()

    pdiv = ia_go_table(df_one, "l", "Key P&L elements from BSE")
    pdiv2 = ia_go_table(df_two, "l", "Key metrics derived from P&L")
    msg = "Working on it"

    return (pdiv, pdiv2, msg)


def ia_reset_returns(ip_df, cycles):
    if ip_df is None or ip_df.empty or not cycles or len(ip_df.columns) == 0:
        return pd.DataFrame()

    op_df = pd.DataFrame(index=ip_df.index)
    print("$$$$$$$$")
    print(cycles)
    print("$$$$$$$$")

    for ctr in range(0, len(cycles)):
        for col in ip_df.columns[0:-1]:
            cname = col + " " + str(ctr)
            op_df[cname] = np.nan

    for ctr in range(0, len(cycles)):
        try:
            s_iloc = cycles[ctr][2]
            e_iloc = cycles[ctr][3]
            for col in ip_df.columns[0:-1]:
                cname = col + " " + str(ctr)
                if s_iloc < len(ip_df.index):
                    base_val = ip_df[col].iloc[s_iloc]
                    if base_val != 0 and not pd.isna(base_val):
                        sub_slice = ip_df[col].iloc[s_iloc:e_iloc + 1]
                        op_df.iloc[s_iloc:e_iloc + 1, op_df.columns.get_loc(cname)] = 100 * sub_slice / base_val
        except Exception:
            pass

    return op_df


def ia_calc_risk_metrics(prices_df, cycles):
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
            if phase == len(cycles) - 1:
                ed_iloc = -1
            else:
                ed_iloc = cycles[phase][3]

            rm_df.loc[phase, "Phase"] = phase
            if sd_iloc < len(prices_df.index):
                actual_ed_iloc = ed_iloc if (ed_iloc != -1 and ed_iloc < len(prices_df.index)) else len(prices_df.index) - 1
                rm_df.loc[phase, "Start Date"] = prices_df.index[sd_iloc].date()
                rm_df.loc[phase, "End Date"] = prices_df.index[actual_ed_iloc].date()

                mini_df = prices_df.iloc[sd_iloc:ed_iloc] if ed_iloc != -1 else prices_df.iloc[sd_iloc:]
                if not mini_df.empty and len(mini_df) > 1:
                    mini_ret_df = np.log(mini_df / mini_df.shift(1)).dropna()
                    cov_mtx = mini_ret_df.cov()
                    if not cov_mtx.empty and cov_mtx.shape[0] > 1 and cov_mtx.iloc[0, 0] != 0:
                        rm_df.loc[phase, "beta"] = np.round(cov_mtx.iloc[1, 0] / cov_mtx.iloc[0, 0], 2)

                s_start = prices_df[stk_idx].iloc[sd_iloc]
                s_end = prices_df[stk_idx].iloc[actual_ed_iloc]
                m_start = prices_df[mkt_idx].iloc[sd_iloc]
                m_end = prices_df[mkt_idx].iloc[actual_ed_iloc]

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
            mini_df = prices_df.iloc[0:-1]
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
        fig = go.Figure()
        fig.update_layout(title=title + " (No Data Available)", paper_bgcolor="hsl(220,25%,18%)", font=dict(color="white"))
        return plot(fig, output_type='div')

    fig = go.Figure()

    if size == "s":
        wd = 800
        ht = 450
    elif size == "m":
        wd = 1600
        ht = 1600
    else:
        wd = 1100
        ht = max(100, 29 * (rm_df.shape[0]))

    fig.add_trace(go.Table(
        header=dict(values=list(rm_df.columns),
                    align='center',
                    fill=dict(color="black")),
        cells=dict(values=rm_df.transpose(),
                   align='center',
                   fill=dict(color="grey")),
    ))

    fig.update_layout(width=wd, height=ht)
    fig.update_layout(paper_bgcolor="hsl(220,25%,18%)",
                      font=dict(color="white"),
                      title=title)

    return plot(fig, output_type='div')


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
        short_name = long_name
    else:
        coname = str(ia_sinfo.stock_name_code_map[long_name][2]).split()
        if len(coname) > 1:
            coname = coname[0] + " " + coname[1]
        else:
            coname = coname[0]
        short_name = coname[0:min(len(coname), 15)]

    return short_name


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
        fig.update_layout(title=title + " (Insufficient Data)", paper_bgcolor="hsl(220,25%,18%)", font=dict(color="white"))
        empty_div = plot(fig, output_type='div')
        return (empty_div, empty_div, empty_div)

    port_df = change_headers(port_df)
    cov_df, beta_list, corr_df, pret_df = get_beta_port(port_df)
    port_df = port_df.drop([port_df.columns[0]], axis=1)

    if port_df.empty or len(port_df.columns) == 0:
        fig = go.Figure()
        fig.update_layout(title=title + " (Insufficient Data)", paper_bgcolor="hsl(220,25%,18%)", font=dict(color="white"))
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

    wd = 1000
    ht = 800

    pca_df = pd.DataFrame(pca_result if len(pca_result) == len(st_series) else np.zeros((len(st_series), 2)), columns=["dim1", "dim2"])
    pca_df["stock"] = st_series.index.tolist()
    pca_df["sector"] = cluster_list if len(cluster_list) == len(pca_df) else ["Cluster 1"] * len(pca_df)
    pca_df["size"] = en_series.values.tolist()
    pca_df["size"] = pca_df["size"].fillna(1.0)

    fig_scat = px.scatter(pca_df, x="dim1", y="dim2", size="size", color="sector", hover_name="stock")
    fig_scat.update_layout(width=wd, height=ht)

    fig = px.treemap(mini_df, path=["sector", "stock", "gain"], values="end", color="beta",
                     color_continuous_scale='RdBu_r')
    fig.update_layout(width=wd, height=ht)

    if not corr_df.empty:
        corr_df["cmean"] = corr_df.mean(axis=1)
        rmean = corr_df.mean(axis=0)
        corr_df.loc["rmean"] = rmean.values.tolist()
        corr_df = corr_df.sort_values(axis=0, by=["cmean"])
        corr_df = corr_df.sort_values(axis=1, by=["rmean"])
        fig_corr = go.Figure()
        fig_corr.add_trace(go.Heatmap(z=corr_df.values, x=corr_df.index.values, y=corr_df.columns.values))
        fig_corr.update_layout(width=corr_df.shape[0] * 30, height=corr_df.shape[0] * 30)
    else:
        fig_corr = go.Figure()

    return (plot(fig, output_type='div'), plot(fig_corr, output_type='div'), plot(fig_scat, output_type='div'))


def ia_go_graph(prices_df, mode, m2, y_scale, title):
    if prices_df is None or prices_df.empty or len(prices_df.columns) == 0 or len(prices_df) == 0:
        fig = go.Figure()
        fig.update_layout(title=title + " (No Data Available)", paper_bgcolor="hsl(220,25%,18%)", font=dict(color="white"))
        return plot(fig, output_type='div')

    wd = 1100
    ht = 600

    try:
        first_series = prices_df[prices_df.columns[0]].dropna()
        mx = np.nanmax(first_series) if len(first_series) > 0 else 100
        mn = np.nanmin(first_series) if len(first_series) > 0 else 1
        for col in prices_df.columns[1:-1]:
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

    fig = go.Figure()

    if mode == 1 and len(prices_df.columns) > 0:
        fig.add_trace(go.Scatter(x=prices_df.index, y=(round(mx * 1.05, 0)) * prices_df[prices_df.columns[-1]],
                                 line_color='hsl(0,90%,90)', fill='tozeroy', mode='lines', name=str(prices_df.columns[-1])))

    ctr = 0
    for col in prices_df.columns[0:-1]:
        if m2 == 0:
            fig.add_trace(
                go.Scatter(x=prices_df.index, y=prices_df[col], line_color='hsl(' + str(360 - ctr * 120) + ',100%,45%)',
                           mode='lines', name=str(col)))
        elif m2 == 1:
            fig.add_trace(go.Scatter(x=prices_df.index, y=prices_df[col],
                                     line_color='hsl(' + str(360 - (ctr % 2) * 120) + ',' + str(
                                         100 - (ctr % 4) * 5) + '%,' + str(54 - (ctr % 4) * 4) + '%)', mode='lines',
                                     name=str(col)))
        elif m2 == "b":
            fig.add_trace(go.Scatter(x=prices_df.index, y=prices_df[col],
                                     line_color='hsl(' + str(240) + ',' + str(100 - (ctr % 4) * 5) + '%,' + str(
                                         54 - (ctr % 4) * 4) + '%)', mode='lines', name=str(col)))
        elif m2 == "r":
            fig.add_trace(go.Scatter(x=prices_df.index, y=prices_df[col],
                                     line_color='hsl(' + str(360) + ',' + str(100 - (ctr % 4) * 5) + '%,' + str(
                                         54 - (ctr % 4) * 4) + '%)', mode='lines', name=str(col)))
        else:
            fig.add_trace(go.Scatter(x=prices_df.index, y=prices_df[col],
                                     line_color='hsl(' + str(360) + ',' + str(100 - (ctr % 4) * 5) + '%,' + str(
                                         54 - (ctr % 4) * 4) + '%)', mode='lines', name=str(col)))
        ctr = ctr + 1

    try:
        if y_scale == "log":
            low_r = math.log(max(0.01, round(mn * .95, 2)), 10)
            high_r = math.log(max(0.02, round(mx * 1.05, 2)), 10)
            fig.update_yaxes(range=[low_r, high_r])
        else:
            fig.update_yaxes(range=[round(mn * .95, 2), round(mx * 1.05, 2)])
    except Exception:
        pass

    fig.update_layout(width=wd, height=ht)
    fig.update_layout(paper_bgcolor="hsl(220,25%,18%)",
                      font=dict(color="white"),
                      title=title,
                      showlegend=False)
    fig.update_xaxes(mirror=True)
    try:
        fig.update_yaxes(mirror=True, type=y_scale)
    except Exception:
        fig.update_yaxes(mirror=True)

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
