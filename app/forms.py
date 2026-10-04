from django import forms
import datetime
from datetime import timedelta
from .models import c_entry_model2, coffee_can_model, co_fin_model
from . import ia_stock_index_info as ia_stat
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column

indices = ia_stat.indices
exchange = ia_stat.exchange
stocks = ia_stat.stocks
latest_date = datetime.date.today()
edate = latest_date - timedelta(days=1)
sdate = edate - timedelta(days=15*365.25)

class ceform_scale(forms.ModelForm):

    sdate = forms.DateField(initial=sdate,label='Start Date', widget=forms.DateInput(attrs={'type': 'date'}))
    edate = forms.DateField(initial=edate,label='End Date',widget=forms.DateInput(attrs={'type': 'date'}))
    benchmark = forms.ChoiceField(initial= ia_stat.def_index,label='Benchmark', choices=indices)
    stock_index = forms.ChoiceField(initial= ia_stat.def_stock, label='Stock/Index', choices=stocks)
    yaxis_type = forms.ChoiceField(initial= ia_stat.def_yaxis, label='Y-axis Scale', choices=ia_stat.yaxis_type)

    class Meta:
        model = c_entry_model2
        fields = ["benchmark", "stock_index", "sdate", "edate", "yaxis_type"]
        ''' widgets = {
            'benchmark': forms.ChoiceField(attrs={ 'style': 'background-color: black'}),
            'stock_index': forms.ChoiceField(attrs={'style': 'background-color: black'}),
            'yaxis_type': forms.ChoiceField(attrs={'style': 'background-color: black'})
        }
        '''

class coffee_can_form(forms.ModelForm):

    sdate = forms.DateField(initial=sdate,label='Start Date', widget=forms.DateInput(attrs={'type': 'date'}))
    edate = forms.DateField(initial=edate,label='End Date',widget=forms.DateInput(attrs={'type': 'date'}))
    benchmark = forms.ChoiceField(initial= ia_stat.def_index,label='Benchmark', choices=indices)
    ccan_port_file = forms.FileField(label="Upload Portfolio", help_text='Upload stock portfolio in excel template')
    yaxis_type = forms.ChoiceField(initial= ia_stat.def_yaxis, label='Y-axis Scale', choices=ia_stat.yaxis_type)

    class Meta:
        model = coffee_can_model
        fields = ["benchmark", "ccan_port_file", "sdate", "edate", "yaxis_type"]


class co_financials_form(forms.ModelForm):

    exchange = forms.ChoiceField(initial= ia_stat.def_exchange,label='Exchange', choices=exchange)
    company = forms.ChoiceField(initial= ia_stat.def_stock, label='Stock', choices=stocks)
    sdate = forms.DateField(initial=sdate,label='Start Date', widget=forms.DateInput(attrs={'type': 'date'}))
    edate = forms.DateField(initial=edate,label='End Date',widget=forms.DateInput(attrs={'type': 'date'}))


    class Meta:
        model = co_fin_model
        fields = ["exchange", "company", "sdate", "edate"]
