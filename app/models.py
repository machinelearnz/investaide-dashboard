# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class c_entry_model2(models.Model):
    benchmark = models.CharField(max_length=200)
    stock_index = models.CharField(max_length=200)
    sdate = models.DateField()
    edate = models.DateField()
    yaxis_type = models.CharField(max_length=20)

class coffee_can_model(models.Model):
    portfolio_excel = models.FileField(upload_to='ccanport/%Y/%m/%d')
    benchmark = models.CharField(max_length=200)
    sdate = models.DateField()
    edate = models.DateField()
    yaxis_type = models.CharField(max_length=20)

class co_fin_model(models.Model):
    exchange = models.CharField(max_length=200)
    company = models.CharField(max_length=200)
    sdate = models.DateField()
    edate = models.DateField()
