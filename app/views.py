# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.template import loader
from django.http import HttpResponse, JsonResponse
from django import template
from .forms import ceform_scale, coffee_can_form, co_financials_form
from . import ia_stockcharts
from . import ia_stock_index_info as ia_sinfo
import pandas as pd
import os
import gc
import urllib.parse
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
import datetime as dt


def ticker_search(request):
    """
    Live ticker search API for autocomplete.
    Searches preconfigured local database (~700 stocks) first for instant response,
    then queries Yahoo Finance search API for any newly listed or global equities.
    """
    q = request.GET.get('q', '').strip()
    if not q or len(q) < 1:
        return JsonResponse({'results': []})

    results = []
    seen = set()
    q_lower = q.lower()

    # 1. Local Search from preconfigured stocks
    try:
        # Exact symbol match first
        for sym, name in ia_sinfo.stocks:
            clean_sym = sym.replace(".NS", "").replace(".BO", "").lower()
            if sym.lower() == q_lower or clean_sym == q_lower:
                seen.add(sym)
                results.append({
                    "symbol": sym,
                    "name": name,
                    "exch": "NSE" if sym.endswith(".NS") else "BSE"
                })

        # Starts-with match (symbol or name)
        for sym, name in ia_sinfo.stocks:
            if sym in seen:
                continue
            clean_sym = sym.replace(".NS", "").replace(".BO", "").lower()
            if clean_sym.startswith(q_lower) or name.lower().startswith(q_lower):
                seen.add(sym)
                results.append({
                    "symbol": sym,
                    "name": name,
                    "exch": "NSE" if sym.endswith(".NS") else "BSE"
                })
                if len(results) >= 8:
                    break

        # Substring match (symbol or name)
        if len(results) < 8:
            for sym, name in ia_sinfo.stocks:
                if sym in seen:
                    continue
                if q_lower in sym.lower() or q_lower in name.lower():
                    seen.add(sym)
                    results.append({
                        "symbol": sym,
                        "name": name,
                        "exch": "NSE" if sym.endswith(".NS") else "BSE"
                    })
                    if len(results) >= 8:
                        break
    except Exception as e:
        print(f"Local ticker search note: {e}")

    # 2. Yahoo Finance Search (if fewer than 6 local results, or to find newly listed/global stocks)
    if len(results) < 6:
        try:
            from curl_cffi import requests as cffi_req
            session = cffi_req.Session(impersonate="chrome")
            enc_q = urllib.parse.quote_plus(q)
            url = f"https://query2.finance.yahoo.com/v1/finance/search?q={enc_q}&quotesCount=8&newsCount=0&region=IN&lang=en-IN"
            r = session.get(url, timeout=3)
            if r.status_code == 200:
                data = r.json()
                quotes = data.get('quotes', [])
                for item in quotes:
                    sym = item.get('symbol')
                    if not sym or sym in seen:
                        continue
                    qtype = item.get('quoteType', '')
                    if qtype not in ('EQUITY', 'ETF', 'INDEX', 'MUTUALFUND'):
                        continue
                    cname = item.get('shortname') or item.get('longname') or sym
                    raw_exch = item.get('exchange', '')
                    exch = 'NSE' if sym.endswith('.NS') or raw_exch in ('NSI', 'NSE') else ('BSE' if sym.endswith('.BO') or raw_exch in ('BSE', 'BSI') else raw_exch)
                    seen.add(sym)
                    results.append({
                        "symbol": sym,
                        "name": cname,
                        "exch": exch
                    })
                    if len(results) >= 10:
                        break
        except Exception as e:
            print(f"Yahoo ticker search fallback note: {e}")

    return JsonResponse({'results': results})


def index(request):

    placeholder_msg = '<div style="padding: 3rem 1rem; text-align: center; color: #64748B; font-size: 0.8125rem;"><i class="fas fa-chart-line mb-2" style="font-size: 1.5rem; opacity: 0.5; display: block;"></i>Configure parameters above and click <strong>Run Analysis</strong> to generate model outputs.</div>'
    plot_div_reset = placeholder_msg
    tbl_div_reset_beta = ""
    tbl_div_eps = ""
    tbl_div_financials = ""
    tbl_div_expectations = ""
    plot_div_financial_trends = ""
    plot_div_eps_growth = ""
    plot_div_ttm_eps = ""
    plot_div_norm = ""
    plot_div_stock = ""
    plot_div_ben = ""

    form = ceform_scale(request.POST or None)
    message = "Please Enter field details"
    msg2 = ""
    print("%%%%", "Here1")
    html_template = loader.get_template( 'index.html' )
    if form.is_valid():
        d1 = form.cleaned_data
        print("######",d1)
        print("%%%%", "Here2")
        ben = d1['benchmark']
        si = d1['stock_index']
        sdate = d1['sdate']
        edate = d1['edate']
        yaxis_type = d1['yaxis_type']
        cycle_type = d1.get('cycle_type', 'bull_bear')
        try:
            form.save()
        except Exception as e:
            print(f"Note: form.save() skipped ({e})")
        cycle_label_map = {
            "bull_bear": "market cycles",
            "calendar_year": "calendar years",
            "financial_year": "financial years",
            "quarterly": "quarters",
            "monthly": "months",
        }
        cycle_name = cycle_label_map.get(cycle_type, "market cycles")
        
        # Safe resolution of company names (prevent KeyError on custom tickers)
        ben_name = ia_sinfo.stock_name_code_map.get(ben, [None, None, ben])[2]
        si_name = ia_sinfo.stock_name_code_map.get(si, [None, None, None])[2]
        if not si_name:
            try:
                import yfinance as yf
                _sess = None
                try:
                    from curl_cffi import requests as cffi_req
                    _sess = cffi_req.Session(impersonate="chrome")
                except Exception:
                    pass
                _t = yf.Ticker(si, session=_sess) if _sess else yf.Ticker(si)
                _inf = _t.info or {}
                si_name = _inf.get('shortName') or _inf.get('longName') or si
            except Exception:
                si_name = si

        message = f"Compare : {ben_name} vs. {si_name} across {cycle_name}"

        plot_div_reset, tbl_div_reset_beta, tbl_div_eps, plot_div_eps_growth, plot_div_ttm_eps, plot_div_norm, plot_div_stock, plot_div_ben, msg2 = ia_stockcharts.ia_plot_prices([ben, si], sdate, edate, yaxis_type, cycle_type=cycle_type)
        
        # Check if ticker price fetching failed
        if msg2 and "Unable to fetch price data" in str(msg2):
            message = f"⚠️ Could not retrieve price history for ticker '{si}'. Please check symbol spelling or select from search suggestions."

        plot_div_financial_trends = ia_stockcharts.ia_go_annual_financial_trends_chart(si, sname=si_name)
        tbl_div_financials = ia_stockcharts.ia_get_company_financials_widget(si, sname=si_name)
        tbl_div_expectations = ia_stockcharts.ia_get_security_expectations_widget(si, sname=si_name)

    else:
        print("%%%%", "Here3")
        print("invalid")
        print(form.errors)

    context = {'bsp_sel_form': form, 'msg': message, 'msg2': msg2, 'plot_div_reset': plot_div_reset, 'tbl_div_reset_beta': tbl_div_reset_beta, 'tbl_div_eps': tbl_div_eps, 'plot_div_financial_trends': plot_div_financial_trends, 'tbl_div_financials': tbl_div_financials, 'tbl_div_expectations': tbl_div_expectations, 'plot_div_eps_growth': plot_div_eps_growth, 'plot_div_ttm_eps': plot_div_ttm_eps, 'plot_div_norm': plot_div_norm, 'plot_div_stock': plot_div_stock, 'plot_div_ben': plot_div_ben}
    context['segment'] = 'index'
    print("%%%%", "Here4")
    resp = render(request, "index.html", context)
    gc.collect()
    return resp

def ccan(request):

    placeholder_msg = '<div style="padding: 3rem 1rem; text-align: center; color: #64748B; font-size: 0.8125rem;"><i class="fas fa-gift mb-2" style="font-size: 1.5rem; opacity: 0.5; display: block;"></i>Upload an Excel allocation file and click <strong>Simulate</strong> to run the Coffee Can backtest.</div>'
    plot_div_reset = placeholder_msg
    tbl_div_reset_beta = ""
    plot_div_norm = ""
    plot_div_stock = ""
    plot_div_ben = ""
    plot_div_scat = ""

    form = coffee_can_form(request.POST or None, request.FILES or None)
    message = "Please upload portfolio & fill details"
    msg2 = ""
    msg_list = ""
    print("%%%%", "Here1")
    #html_template = loader.get_template( 'index.html' )
    if form.is_valid():
        d1 = form.cleaned_data
        #print("######",d1)
        print("%%%%", "Here2coffee")
        ben = d1['benchmark']
        port_xl_data = request.FILES['ccan_port_file']
        tpath = default_storage.save('port_xls.xlsx', ContentFile(port_xl_data.read()))
        #print("$$$$$$", type(port_xl))
        print("^^^^^", request.FILES)
        sdate = d1['sdate']
        edate = d1['edate']
        yaxis_type = d1['yaxis_type']

        #fname = r"D:\Backup\Rohit\Work\New Technologies\Cookie Can Portfolio\Black Dashboard\black-dashboard-django\Portfolio Template.xlsx"
        fname = os.path.join(settings.MEDIA_ROOT, tpath)
        ccan_port_df = pd.read_excel(fname, sheet_name="Portfolio", engine="openpyxl")
        ccan_port_df = ccan_port_df.loc[ccan_port_df['company']!= "x"]
        ccan_port_df = ccan_port_df[ccan_port_df['company'].notna()]
        print(ccan_port_df)

        form.save()
        message = "Compare : Portfolio vs. " + ia_sinfo.stock_name_code_map[ben][2] +" across market cycles"

        plot_div_reset, tbl_div_reset_beta, tbl_div_fin, plot_div_norm,plot_div_stock, plot_div_ben, plot_div_scat, msg2, msg_list = ia_stockcharts.ia_plot_port_prices([ben], sdate,edate,yaxis_type,ccan_port_df)
        #plot_div1, plot_div2, plot_div3, plot_div4,plot_div5, plot_div6 = ia_stockcharts.ia_plot_prices([ben, si], sdate,edate,yaxis_type)
        #plot_div1, plot_div2, plot_div3, plot_div4,plot_div5, plot_div6 = ia_stockcharts.ia_plot_prices([ben, si], sdate,edate)

    else:
        print("%%%%", "Form Invalid - views")
        print(form.errors)

    context = {'bsp_sel_form':form,'msg': message,'msg2':msg2, 'msg_list':msg_list,'plot_div_reset': plot_div_reset , 'tbl_div_reset_beta': tbl_div_reset_beta, 'plot_div_norm': plot_div_norm, 'plot_div_stock': plot_div_stock, 'plot_div_ben': plot_div_ben, 'plot_div_scat': plot_div_scat}
    context['segment'] = 'coffee-can'
    print("%%%%", "Completing views and returning ...")
    resp = render(request,"coffee-can.html", context)
    gc.collect()
    return resp

def cofin(request):

    tbl_div_fin = "<div><h6 style=\"text-align:center; color:yellow;\"> </h6></div>"
    tbl_div_fin2 = "<div><h6 style=\"text-align:center; color:yellow;\"> </h6></div>"

    form = co_financials_form(request.POST or None)
    message = "Please provide details"
    msg2 = ""
    msg_list = ""
    print("%%%%", "Here1")
    #html_template = loader.get_template( 'index.html' )
    if form.is_valid():
        d1 = form.cleaned_data
        #print("######",d1)
        print("%%%%", "Here2coffee")
        exch = d1['exchange']
        comp = d1['company']
        sdate = d1['sdate']
        edate = d1['edate']

        form.save()
        message = "Get financials of  ..." + ia_sinfo.stock_name_code_map[comp][2] +" across market cycles"

        tbl_div_fin, tbl_div_fin2, msg2= ia_stockcharts.ia_get_financials(comp, exch, sdate,edate)

    else:
        print("%%%%", "Form Invalid - views")
        print(form.errors)

    context = {'bsp_sel_form': form, 'msg': message, 'msg2': msg2, 'tbl_div_fin': tbl_div_fin, 'tbl_div_fin2': tbl_div_fin2, 'tbl_div_financials': tbl_div_fin}
    context['segment'] = 'index'
    #return HttpResponse(html_template.render(context, request))
    print("%%%%", "Completing views and returning ...")
    return render(request,"co_fins.html", context)

def pages(request):
    context = {}
    # All resource paths end in .html.
    # Pick out the html file name from the url. And load that template.
    try:
        
        load_template      = request.path.split('/')[-1]
        context['segment'] = load_template

        html_template = loader.get_template( load_template )
        return HttpResponse(html_template.render(context, request))
        
    except template.TemplateDoesNotExist:

        html_template = loader.get_template( 'page-404.html' )
        return HttpResponse(html_template.render(context, request))

    except:
    
        html_template = loader.get_template( 'page-500.html' )
        return HttpResponse(html_template.render(context, request))
