#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install production dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Collect static files into staticfiles/ directory for WhiteNoise
python manage.py collectstatic --no-input

# Run any outstanding database migrations
python manage.py migrate
