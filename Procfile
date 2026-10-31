web: gunicorn core.wsgi:application --worker-class gthread --workers 1 --threads 4 --max-requests 500 --max-requests-jitter 50 --timeout 120 --keep-alive 5
