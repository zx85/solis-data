#!/bin/bash
python /usr/local/scripts/octopusday.py $(date -d "Yesterday" "+%Y-%m-%d") | tee /usr/local/scripts/octopusday.log 2>&1
