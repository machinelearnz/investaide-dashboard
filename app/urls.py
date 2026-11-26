# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django.urls import path, re_path
from app import views

urlpatterns = [

    # The home page
    path('', views.index, name='home'),
    path('api/ticker-search/', views.ticker_search, name='ticker_search'),
    path('api/ai-analysis-json/', views.export_ai_analysis_json, name='ai_analysis_json'),
    path('coffee-can.html', views.ccan, name='coffee'),
    path('co_fins.html', views.cofin, name='cofin'),

    # Matches any html file
    re_path(r'^.*\.*', views.pages, name='pages'),

]
