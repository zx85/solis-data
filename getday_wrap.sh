#!/bin/bash

source /usr/local/scripts/solis-data/solis.env
cd /usr/local/scripts/solis-data || exit 1
timeout 2m /home/james/.local/bin/uv run python /usr/local/scripts/solis-data/getday.py $(date -d "Yesterday" "+%Y-%m-%d") > /usr/local/scripts/solis-data/getday.log 2>&1
