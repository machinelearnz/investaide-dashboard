# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.template import loader
from django.http import HttpResponse
from django import template
from .forms import ceform_scale, coffee_can_form, co_financials_form
from django.shortcuts import render
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from plotly.offline import plot
from plotly.graph_objs import Scatter
from . import ia_stockcharts
from . import ia_stock_index_info as ia_sinfo
import pandas as pd
import os
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
import datetime as dt

def index(request):


    plot_div_reset= "<div><h4 style=\"text-align:center; color:yellow;\"><b> </b></h4></div>"
    tbl_div_reset_beta= "<div><h4 style=\"text-align:center; color:yellow;\"><b> </b></h4></div>"
    tbl_div_fin= "<div><h4 style=\"text-align:center; color:yellow;\"><b> </b></h4></div>"
    plot_div_norm= "<div><h4 style=\"text-align:center; color:yellow;\"><b> </b></h4></div>"
    plot_div_stock= "<div><h4 style=\"text-align:center; color:yellow;\"><b> </b></h4></div>"
    plot_div_ben = "<div><h4 style=\"text-align:center; color:yellow;\"><b> </b></h4></div>"
    #plot_div_reset, tbl_div_reset_beta, tbl_div_fin, plot_div_norm, plot_div_stock, plot_div_ben = ia_stockcharts.ia_plot_prices( ["^NSEI", "ITC.NS"], dt.datetime.now().date() - :dt.timedelta(days=365.5*15) , dt.datetime.now().date() - dt.timedelta(days=1), "log")

    form = ceform_scale(request.POST or None)
    message = "Please Enter field details"
    msg2 = ""
    #message = "Chart of : NSE vs. ITC Limited"
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
        form.save()
        message = "Compare : " + ia_sinfo.stock_name_code_map[ben][2] +  " vs. " + ia_sinfo.stock_name_code_map[si][2] + " across market cycles"

        plot_div_reset, tbl_div_reset_beta, tbl_div_fin, plot_div_norm,plot_div_stock, plot_div_ben,msg2 = ia_stockcharts.ia_plot_prices([ben, si], sdate,edate,yaxis_type)
        #plot_div1, plot_div2, plot_div3, plot_div4,plot_div5, plot_div6 = ia_stockcharts.ia_plot_prices([ben, si], sdate,edate,yaxis_type)
        #plot_div1, plot_div2, plot_div3, plot_div4,plot_div5, plot_div6 = ia_stockcharts.ia_plot_prices([ben, si], sdate,edate)

    else:
        print("%%%%", "Here3")
        print("invalid")
        print(form.errors)

    context = {'bsp_sel_form':form,'msg': message,'msg2': msg2, 'plot_div_reset': plot_div_reset , 'tbl_div_reset_beta': tbl_div_reset_beta, 'plot_div_norm': plot_div_norm, 'plot_div_stock': plot_div_stock, 'plot_div_ben': plot_div_ben}
    context['segment'] = 'index'
    #return HttpResponse(html_template.render(context, request))
    print("%%%%", "Here4")
    return render(request,"index.html", context)

def ccan(request):

    plot_div_reset = "<div><h6 style=\"text-align:center; color:yellow;\"> </h6></div>"
    tbl_div_reset_beta = "<div><h6 style=\"text-align:center; color:yellow;\"> </h6></div>"
    plot_div_norm = "<div><h6 style=\"text-align:center; color:yellow;\"> </h6></div>"
    plot_div_stock = "<div><h6 style=\"text-align:center; color:yellow;\"> </h6></div>"
    plot_div_ben = "<div><h6 style=\"text-align:center; color:yellow;\"> </h6></div>"
    plot_div_scat = "<div><h6 style=\"text-align:center; color:yellow;\"> </h6></div>"

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
    context['segment'] = 'index'
    #return HttpResponse(html_template.render(context, request))
    print("%%%%", "Completing views and returning ...")
    return render(request,"coffee-can.html", context)

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

    context = {'bsp_sel_form':form,'msg': message,'msg2':msg2,'tbl_div_fin': tbl_div_fin,'tbl_div_fin2': tbl_div_fin2 }
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
