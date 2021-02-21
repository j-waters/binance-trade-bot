#!/usr/bin/env bash

python crypto_trading.py &
gunicorn api_server:app -w 1 --threads 1 -b 0.0.0.0:8000
