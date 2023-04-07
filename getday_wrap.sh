#!/bin/bash

source /usr/local/scripts/solis-data/solis.env
/usr/bin/python3 /usr/local/scripts/solis-data/getday.py $(date -d "Yesterday" "+%Y-%m-%d") > /usr/local/scripts/solis-data/getday.log 2>&1
