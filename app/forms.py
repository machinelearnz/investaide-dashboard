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

    sdate = forms.DateField(initial=sdate, label='Start Date', widget=forms.DateInput(attrs={'type': 'date'}))
    edate = forms.DateField(initial=edate, label='End Date', widget=forms.DateInput(attrs={'type': 'date'}))
    benchmark = forms.ChoiceField(initial=ia_stat.def_index, label='Benchmark', choices=indices)
    stock_index = forms.CharField(
        initial="CRISIL.NS",
        label='Stock / Security (Search or Type Ticker)',
        widget=forms.TextInput(attrs={
            'placeholder': 'Type company name or ticker (e.g. Tata Motors, Swiggy, INFY.NS)...',
            'autocomplete': 'off',
            'id': 'id_stock_index'
        })
    )
    yaxis_type = forms.ChoiceField(initial=ia_stat.def_yaxis, label='Y-axis Scale', choices=ia_stat.yaxis_type)
    cycle_type = forms.ChoiceField(initial=ia_stat.def_cycle_type, label='Cycle Breakdown', choices=ia_stat.cycle_types)

    def clean_stock_index(self):
        si = self.cleaned_data.get('stock_index', '').strip()
        if not si:
            raise forms.ValidationError("Please enter a stock ticker or company name.")
        # If user picked formatted item like "TCS.NS - TATA CONSULTANCY SERVICES"
        if " - " in si:
            si = si.split(" - ")[0].strip()
        elif " (" in si and si.endswith(")"):
            si = si.split(" (")[0].strip()
        elif " [" in si and si.endswith("]"):
            si = si.split(" [")[0].strip()
        si = si.split()[0].strip().upper()
        # Auto-append .NS if bare symbol like "ZOMATO" or "RELIANCE" without dot or ^
        if not si.startswith("^") and "." not in si:
            if f"{si}.NS" in ia_stat.stock_name_code_map:
                si = f"{si}.NS"
            else:
                us_tech = {"AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "TSLA", "NFLX", "INTC", "AMD"}
                if si not in us_tech:
                    si = f"{si}.NS"
        return si

    class Meta:
        model = c_entry_model2
        fields = ["benchmark", "stock_index", "sdate", "edate", "yaxis_type", "cycle_type"]


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
