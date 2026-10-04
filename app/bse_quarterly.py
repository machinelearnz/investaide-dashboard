import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime as dt
import pandas_datareader as wb
import yfinance as yf
from dateutil.relativedelta import relativedelta

#url = "https://www.bseindia.com/corporates/results.aspx?Code=500043&Company=DIVIS+LABORATORIES+LTD.&qtr=108.00&RType="
#header = { 'user-agent': 'Mozilla/5.0 (iPad; CPU OS 11_0 like Mac OS X) AppleWebKit/604.1.34 (KHTML, like Gecko) Version/11.0 Mobile/15A5341f Safari/604.1'}

exch_url_template_map = {
    "bse": ["https://www.bseindia.com/corporates/results.aspx?Code=", "&Company=","&qtr=","&RType="]
}

exch_header_template_map = {
    "bse": { 'user-agent': 'Mozilla/5.0 (iPad; CPU OS 11_0 like Mac OS X) AppleWebKit/604.1.34 (KHTML, like Gecko) Version/11.0 Mobile/15A5341f Safari/604.1'}
}

def get_exch_url(exchange, ccode, cname,qtr):
    url = exch_url_template_map[exchange][0]+str(ccode)+exch_url_template_map[exchange][1]+cname.replace(" ", "+")+exch_url_template_map[exchange][2]+'{0:.2f}'.format(qtr)+exch_url_template_map[exchange][3]

    return url

def get_exch_header(exchange):
    header = exch_header_template_map[exchange]

    return header

def get_exch_response (exchange, ccode, cname, qtr):

    url = get_exch_url(exchange,ccode,cname,qtr)
    header = get_exch_header(exchange)
    print(">>> Getting Response from ..", url)

    response = requests.get(url, headers=header)

    return response.text


def get_result_table (exchange, result_soup):

    tables = result_soup.find_all('table')
    if exchange == "bse":
        results_table = tables[2]
    else:
        results_table = tables[2]

    res_df = pd.DataFrame(columns=["desc", "value"])

    results_rows = results_table.find_all('tr')

    for row in range(1,len(results_rows)):
        row_data = results_rows[row].find_all('td')
        try:
            term2 = float(row_data[1].text.replace(",",""))
        except:
            term2 = row_data[1].text
        res_df.loc[row] = [row_data[0].text, term2]

    return res_df

def find_idx(indices):
    count = 0
    for val in indices:
        if val == 1:
            break
        else:
            count +=1

    if count == len(indices):
       count = "NF"

    return count

def get_detail_from_table(table_df, string_list,type):

    if type == "O":
        string = ".*"
        for element in string_list:
            string = string + element+".*"

        indices = table_df["desc"].str.contains(string, case = False)
    elif type == "S":
        string = "^"
        for element in string_list:
            string = string + element+".*"

        indices = table_df["desc"].str.contains(string, case = False)
    else:
        indices = table_df["desc"].str.contains("^"+string_list[0])

    idx = find_idx(indices)
    if idx == "NF":
        value =0
    else:
        value = table_df['value'].iloc[idx]

    return value

def exch_get_info(tkr1, arg):

    tkr = yf.Ticker(tkr1)
    info = tkr.info

    if arg == "sh_os":
        value = info["sharesOutstanding"]
    elif arg == "feps":
        value = info["forwardEps"]
    elif arg == "bv":
        value = info["bookValue"]
    elif arg == "teps":
        value = info["trailingEps"]
    else:
        value = 999999

    return value

def fill_shares_outstanding(tkr, sh_os, end_dates):

    tkr = yf.Ticker(tkr)
    actions = tkr.actions
    today = dt.date.today()

    actions["sh_os"] = 0
    actions.loc[today] = [0,0,sh_os]
    length = actions.shape[0]

    for row_inv in range(2,length):
        row = length - row_inv
        if actions["Stock Splits"].loc[actions.index[row]] == 0:
            actions["sh_os"].loc[actions.index[row]] = actions["sh_os"].loc[actions.index[row+1]]
        else:
            actions["sh_os"].loc[actions.index[row]] = actions["sh_os"].loc[actions.index[row+1]]/actions["Stock Splits"].loc[actions.index[row]]

    flist = []


    for ed in end_dates:
        for sday in actions.index:
            if sday >= ed:
                tshos = actions["sh_os"].loc[sday]
                break

        flist.append(tshos)


    return flist



def fill_prices (tkr,end_dates):

    price_list = []
    for ed in end_dates:
        edi = ed
        sdi = edi -relativedelta(days=7)
        try:
            prices = wb.DataReader(tkr, data_source="yahoo", start=sdi, end=edi)['Adj Close']
            sel_price = round(prices.iloc[-1],2)
            price_list.append(sel_price)
        except:
            price_list.append(0)

    return price_list



def exch_get_results (exchange, ccode, cname, qstart,qend,period, ctkr):

    writer = pd.ExcelWriter(r".\qtr_result.xlsx")
    if (cname.find("Bank") == -1):
        summary_df = pd.DataFrame(columns =["stdate","enddate", "netsales","oi", "expenses","exceptional", "pbt", "tax", "pat", "eps","eqcapital", "fv"])
        isbank = 0
    else:
        summary_df = pd.DataFrame(columns=["stdate", "enddate", "intincome", "oi", "intexp","othexp","provisions", "pbt", "tax", "pat", "eps","eqcapital", "fv"])
        isbank = 1
    #print(summary_df)


    lcount = 0
    for qtr in range(qstart, qend+1):
        if(period == "ann"):
            qtr = qtr+0.5

        response = get_exch_response(exchange, ccode,cname,qtr)
        response_soup = BeautifulSoup(response,'html.parser')
        result_table = get_result_table(exchange, response_soup)

        if result_table.shape[0]<=5:
            #No data for the quarter/year
            continue
        result_table.to_excel(writer, index=True, sheet_name=str(qtr))

        #df_qtr = qtr
        df_sdate = get_detail_from_table(result_table,["Date Begin"],"O")
        df_sdate = dt.datetime.strptime(df_sdate, "%d-%b-%y").date()
        df_edate = get_detail_from_table(result_table,["Date End"],"O")
        df_edate = dt.datetime.strptime(df_edate, "%d-%b-%y").date()

        df_ns = get_detail_from_table(result_table,["Net","Sales"],"O")
        df_oi = get_detail_from_table(result_table,["Other Income"],"E")

        if(isbank):
            df_intexp = get_detail_from_table(result_table,["Interest", "Expended"],"O")
            df_othexp = get_detail_from_table(result_table,["Operating", "Expenses"],"O")
            df_prov = get_detail_from_table(result_table,["Provisions", "and", "Contingencies"],"S")
        else:
            df_exp = get_detail_from_table(result_table,["expenditure"],"O")
            df_xcep =  get_detail_from_table(result_table,["Exceptional"],"E")

        df_pbt = get_detail_from_table(result_table,["profit","before","tax"],"O")
        df_tax = get_detail_from_table(result_table,["Tax"],"E")
        df_pat = get_detail_from_table(result_table,["net","profit","after","tax"],"O")
        df_eps = get_detail_from_table(result_table,["basic","eps"],"O")
        df_eqcap = get_detail_from_table(result_table, ["Equity Capital"], "S")
        df_fv = get_detail_from_table(result_table, ["Face Value"], "S")


        if(isbank):
            summary_df.loc[lcount] = [df_sdate, df_edate, df_ns, df_oi, df_intexp, df_othexp,df_prov, df_pbt, df_tax, df_pat, df_eps, df_eqcap, df_fv]
        else:
            summary_df.loc[lcount] = [df_sdate,df_edate,df_ns,df_oi, df_exp,df_xcep,df_pbt, df_tax, df_pat, df_eps, df_eqcap, df_fv]

        lcount += 1

        #print("^^^", summary_df)

    if period != "ann":

        if (isbank):
            summary_df["ttmintincome"] = round(summary_df["intincome"].rolling(4).sum(),0)
        else:
            summary_df["ttmnetsales"] = round(summary_df["netsales"].rolling(4).sum(),0)

        summary_df["ttmpbt"] = round(summary_df["pbt"].rolling(4).sum(),0)
        summary_df["ttmpat"] = round(summary_df["pat"].rolling(4).sum(),0)

    sh_os = exch_get_info(ctkr, "sh_os")
    #sh_os = 100000
    summary_df["sh_os"] = fill_shares_outstanding(ctkr, sh_os, summary_df["enddate"])
    summary_df["sh_os"] = round(summary_df["sh_os"]/(10**6),0)
    summary_df["price"] = fill_prices(ctkr, summary_df["enddate"])
    summary_df["quick_mcap"] = round(sh_os*summary_df["price"]/(10**6),0)
    summary_df["better_mcap"] = summary_df["quick_mcap"]*(summary_df["eqcapital"]/summary_df["fv"])/summary_df["sh_os"]
    summary_df["better_mcap"] = round(summary_df["better_mcap"],0)

    if period != "ann":
        summary_df["ttm_pe1"] = round(summary_df["quick_mcap"]/summary_df["ttmpat"],2)
        summary_df["ttm_pe2"] = round(summary_df["better_mcap"]/summary_df["ttmpat"],2)
    else:
        summary_df["ttm_pe1"] = round(summary_df["quick_mcap"]/summary_df["pat"],2)
        summary_df["ttm_pe2"] = round(summary_df["better_mcap"]/summary_df["pat"],2)

    summary_df.to_excel(writer, index=False, sheet_name="summary")
    writer.save()

    return summary_df

exchange = "bse"
qstart = 60
qend = 108
ccode = 500790
cname = "Nestle India Ltd."
ctkr = "NESTLEIND.NS"
'''
ccode = 500180
cname = "HDFC Bank Ltd."
ctkr = "HDFCBANK.NS"
'''
#exch_get_results(exchange, ccode, cname, qstart,qend,"qtr", ctkr)
#exch_get_info(ctkr,"sh_os")

