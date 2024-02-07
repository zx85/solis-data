#!/usr/bin/python3
# Testing Octopus tariff stuff
# Maybe I should have done this before changing to agile...
#
# Database tables: octopusIn
# year int
# month int
# day int
# hour int
# minute int
# consumed float
# price float

# environment variables from solis.env
# octopusURL
# octopusTariff
# octopusAPIKey
# octopusMPAN
# octopusSN
# octopusInTable

import os
import sys
import json
from calendar import monthrange
import hashlib
from hashlib import sha1
import hmac
import base64
from datetime import datetime, timedelta
import pytz
import requests
import time
import jmespath
from pathlib import Path

# important - needs to run pip3 install python-mysql-connector
import mysql.connector


# Local time doings
def utc_calc(time_string, day_diff=0):
    local = pytz.timezone("Europe/London")
    naive = datetime.strptime(time_string, "%Y-%m-%d")
    local_dt = local.localize(naive, is_dst=None)
    utc_dt = local_dt.astimezone(pytz.utc) + timedelta(days=day_diff)
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def get_price_data(octopusInfo, date_query):
    # print(f"Getting agile price data for {date_query}...")
    results = {}
    auth = "Basic " + base64.b64encode(
        "sk_live_4EZ0vNYbCgA2gU466C9ygwfY:".encode("UTF-8")
    ).decode("UTF-8")
    url = f"{octopusInfo['URL']}/v1/products/{octopusInfo['Tariff']}/electricity-tariffs/E-1R-{octopusInfo['Tariff']}-C/standard-unit-rates/?period_from={utc_calc(date_query)}&period_to={utc_calc(date_query,1)}"
    # print(f"URL is {url}")
    Session = requests.Session()
    header = {"Authorization": auth}
    try:
        resp = Session.get(url, headers=header, timeout=60)
        results = resp.json()
    except Exception as e:
        print("Agile data request failed because " + str(e))
    return results


def get_consumed_data(octopusInfo, date_query):
    results = {}
    auth = "Basic " + base64.b64encode(
        "sk_live_4EZ0vNYbCgA2gU466C9ygwfY:".encode("UTF-8")
    ).decode("UTF-8")
    url = f"{octopusInfo['URL']}/v1/electricity-meter-points/{octopusInfo['MPAN']}/meters/{octopusInfo['SN']}/consumption/?period_from={utc_calc(date_query)}&period_to={utc_calc(date_query,1)}"
    # print(f"URL is {url}")
    Session = requests.Session()
    header = {"Authorization": auth}
    try:
        resp = Session.get(url, headers=header, timeout=60)
        results = resp.json()
    except Exception as e:
        print("Consumption data request failed because " + str(e))
    return results


def main():

    if len(sys.argv) < 2:
        print("Usage: getoctopus.py yyyy-mm-dd")
        print("eg. getoctopus.py 2023-01-15")
        exit(1)
    date_query = sys.argv[1]

    # Database credentials for the conkers
    dbInfo = {
        "dbuser": os.environ.get("dbUser"),
        "dbpass": os.environ.get("dbPass"),
        "dbhost": os.environ.get("dbHost"),
        "dbname": os.environ.get("dbName"),
        "dbport": os.environ.get("dbPort"),
        "dbtable": os.environ.get("dbTable"),
    }
    # Octopus goodies
    octopusInfo = {
        "URL": os.environ.get("octopusURL"),
        "Tariff": os.environ.get("octopusTariff"),
        "APIKey": os.environ.get("octopusAPIKey"),
        "MPAN": os.environ.get("octopusMPAN"),
        "SN": os.environ.get("octopusSN"),
        "InTable": os.environ.get("octopusInTable"),
    }

    # database bits

    try:
        cnx = mysql.connector.connect(
            user=dbInfo["dbuser"],
            password=dbInfo["dbpass"],
            host=dbInfo["dbhost"],
            port=dbInfo["dbport"],
            database=dbInfo["dbname"],
            auth_plugin="mysql_native_password",
        )
    except Exception as e:
        print("DB select didn't work sorry because " + str(e))
        sys.exit(1)

    table = octopusInfo["InTable"]

    price_data = get_price_data(octopusInfo, date_query)
    consumed_data = get_consumed_data(octopusInfo, date_query)
    if "results" not in price_data or "results" not in consumed_data:
        if "results" not in price_data:
            print("No results in price_data - please try again later")
        if "results" not in consumed_data:
            print("No results in consumed_data - please try again later")
        sys.exit(1)

    for each_result in consumed_data["results"]:
        for each_price in price_data["results"]:
            id = {}
            if each_price["valid_from"] == each_result["interval_start"]:
                # this is where the database stuff comes in
                id["year"] = each_result["interval_start"][:4]
                id["month"] = each_result["interval_start"][5:7]
                id["day"] = each_result["interval_start"][8:10]
                id["hour"] = each_result["interval_start"][11:13]
                id["minute"] = each_result["interval_start"][14:16]
                id["consumed"] = each_result["consumption"]
                id["price"] = each_price["value_inc_vat"]
                placeholders = ", ".join(["%s"] * len(id))
                columns = ", ".join(id.keys())
                sql = "REPLACE INTO %s ( %s ) VALUES ( %s )" % (
                    table,
                    columns,
                    placeholders,
                )
                try:
                    cursor = cnx.cursor()
                    cursor.execute(sql, list(id.values()))
                    cnx.commit()
                    cursor.close()

                except Exception as e:
                    print("The insert didn't work. Here's why: " + str(e))
    cnx.close()


if __name__ == "__main__":
    main()
