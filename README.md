# InvestAide - Investment Insights Dashboard

**InvestAide** is an interactive financial analytics and portfolio dashboard built with **Django**, **Pandas**, **Plotly**, and **yfinance**. It helps investors analyze relative stock valuations and evaluate multi-cycle coffee-can portfolios with automated market cycle detection, risk metrics, and interactive visualizations.

---

## 🚀 Features

### 1. 📊 Relative Stock Analysis
- **Benchmark Comparison:** Compare individual stocks against benchmark indices (e.g., `NIFTY50`, `SENSEX`) over custom date ranges.
- **Market Cycle Detection:** Automatically identifies market peaks and troughs to segment data into bull and bear phases.
- **Cycle-Reset Performance:** Re-normalizes returns across market cycles to evaluate how stocks perform in different market regimes.
- **Risk Metrics & Beta:** Computes covariance, beta, stock returns, and benchmark returns for each individual cycle as well as the full time period.
- **Linear & Logarithmic Scales:** Switch between linear and log-scale interactive Plotly charts.

### 2. 🎁 Coffee-Can Portfolio Analyzer
- **Portfolio Upload:** Upload your custom portfolio holdings via an Excel template (`.xlsx`).
- **Exposure Treemap & Sector Analysis:** Visualizes portfolio weights, gains, and beta distribution using interactive Plotly Treemaps.
- **Machine Learning Clustering:** Groups portfolio companies using K-Means clustering and t-SNE dimensionality reduction based on return correlations.
- **Cross-Cycle Performance:** Tracks aggregate portfolio performance vs. benchmark across market cycles.

---

## 🛠️ Tech Stack

- **Backend:** Python, Django
- **Data Analysis:** Pandas, NumPy, Scikit-Learn, yfinance
- **Data Visualization:** Plotly (Offline / Interactive HTML widgets)
- **Frontend / UI:** Bootstrap 4, Black Dashboard Dark UI Theme

---

## 📁 Project Structure

```text
investaide-dashboard/
├── app/                              # Main application logic
│   ├── forms.py                      # Django forms for stock & portfolio inputs
│   ├── ia_stockcharts.py             # Calculation engine (cycles, beta, Plotly graphs)
│   ├── ia_stock_index_info.py        # Stock code & benchmark mappings
│   ├── models.py                     # Database models
│   ├── urls.py                       # Application URL routing
│   └── views.py                      # View handlers (Relative Value, Coffee-Can)
├── core/                             # Django project core
│   ├── settings.py                   # Django configuration & settings
│   ├── urls.py                       # Root URL routing
│   ├── wsgi.py                       # WSGI entry point
│   ├── static/                       # CSS, JavaScript, fonts, icons, images
│   └── templates/                    # HTML templates
│       ├── index.html                # Relative Stock Analysis page
│       ├── coffee-can.html           # Coffee-Can Portfolio page
│       ├── layouts/                  # Base HTML layout
│       └── includes/                 # Sidebar, navigation, footer, plugin components
├── media/                            # Media storage for portfolio uploads
├── Portfolio Template.xlsx           # Sample Excel template for Coffee-Can upload
├── requirements.txt                  # Python dependencies
├── manage.py                         # Django management CLI
├── .gitignore                        # Git ignore rules
└── README.md                         # Documentation
```

---

## ⚡ Quick Start & Installation

### 1. Clone the Repository
```bash
git clone https://github.com/<your-username>/<your-repo-name>.git
cd <your-repo-name>
```

### 2. Create and Activate Virtual Environment

**On Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**On macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Start the Development Server
```bash
python manage.py runserver 8000
```

Open your browser and navigate to:
👉 **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)**

---

## 📝 Usage Guide

1. **Relative Stock Analysis:**
   - Select a benchmark (e.g. `NIFTY50`) and a target stock.
   - Choose a start date, end date, and Y-axis scale (`Log` or `Linear`).
   - Click **Submit** to view interactive cycle graphs and risk metric tables.

2. **Coffee-Can Portfolio Analysis:**
   - Navigate to **Coffee-Can** from the sidebar.
   - Select your benchmark index, start date, end date, and scale.
   - Upload your holdings spreadsheet (use `Portfolio Template.xlsx` as a format guide).
   - Click **Submit** to view exposure treemaps, cluster scatter plots, and cycle-wise portfolio returns.

---

## 📄 License

This project is licensed under the MIT License.
