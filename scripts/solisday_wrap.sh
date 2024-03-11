#!/bin/bash
python /usr/local/scripts/solis-data/getday.py $(date -d "Yesterday" "+%Y-%m-%d") | tee /usr/local/scripts/solis-data/getday.log 2>&1
