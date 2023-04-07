#!/bin/bash
source /usr/local/scripts/solis-data/solis.env
/usr/bin/python3 /usr/local/scripts/solis-data/getdata.py  > /usr/local/scripts/solis-data/getdata.log 2>&1
