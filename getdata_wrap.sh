#!/bin/bash
source /usr/local/scripts/solis-data/solis.env
cd /usr/local/scripts/solis-data || exit 1
/home/james/.local/bin/uv run python /usr/local/scripts/solis-data/getdata.py  > /usr/local/scripts/solis-data/getdata.log 2>&1
