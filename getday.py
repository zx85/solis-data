#!/usr/bin/python3
import os
import sys
import json
from calendar import monthrange
import hashlib
from hashlib import sha1
import hmac
import base64
from datetime import datetime, timezone, timedelta
import time
import pytz
import requests
import jmespath
from pathlib import Path

# I think this is python-telegram-bot
import telegram

# important - needs to run pip3 install python-mysql-connector
import mysql.connector


# This needs the following environment variables to be created:
#
#
# export solisURL="https://www.soliscloud.com:13333"
# export solisDayPath="/v1/api/stationDayEnergyList"

# export solisKey="YOUR_API_KEY
# export solisSecret="YOUR_API_SECRET"
# export solisId="YOUR_SOLIS_ID"
# export solisSn="YOUR_INVERTER_SERIAL_NUMBER"

# Telegram goodness
# export telegramBotToken="YOUR_TELEGRAM_BOT_TOKEN"
# export telegramChatId="YOUR_PERSONAL_CHAT_ID"

# Database credentials
# export dbUser="YOUR_DB_USER"
# export dbPass="YOUR_DB_PASS"
# export dbHost="YOUR_DB_HOST"
# export dbName="YOUR_DB_NAME" # eg solar
# export dbTable="YOUR_DB_TABLE" # if you use the schema in solarday.sql it will be solarDay
# export dbPort="YOUR_DB_PORT" # normally 3306

# Octopus variables
# export octopusURL="https://api.octopus.energy"
# export octopusTariff="YOUR_OCTOPUS_AGILE_TARIFF"
# export octopusAPIKey="YOUR_OCTOPUS_API_KEY"
# export octopusMPAN="YOUR_SMARTMETER_MPAN"
# export octopusSN="YOUR_SMARTMETER_SERIAL"
# export octopusInTable="YOUR_OCTOPUSIN_TABLE" # normally octopusIn


# Push message doings
def sendmessage(bot, chat_id, thisMessage):
    bot.send_message(chat_id=chat_id, text=thisMessage)


def localtime(inputTime):
    return time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime(inputTime))


# Local time doings
def utc_calc(time_string, day_diff=0):
    local = pytz.timezone("Europe/London")
    naive = datetime.strptime(time_string, "%Y-%m-%d")
    local_dt = local.localize(naive, is_dst=None)
    utc_dt = local_dt.astimezone(pytz.utc) + timedelta(days=day_diff)
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def get_solis_data(solisInfo, date_query):
    # jmespath filter
    jmespathfilter = "data.records[0].{totalConsumed:consumeEnergy, solarGen:produceEnergy, solarExport:gridSellEnergy, batCharge:batteryChargeEnergy, selfUse:oneSelf, gridImport:gridPurchasedEnergy, batUse:batteryDischargeEnergy}"
    solar_usage = {}
    url = solisInfo["solisUrl"]
    CanonicalizedResource = solisInfo["solisPath"]
    req = url + CanonicalizedResource
    VERB = "POST"
    Content_Type = "application/json"
    Session = requests.Session()

    now = datetime.now(timezone.utc)
    Date = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
    Body = (
        '{"time":"'
        + date_query
        + '", "pageSize":100, "sn":"'
        + solisInfo["solisSn"]
        + '", "id":"'
        + solisInfo["solisId"]
        + '"}'
    )
    Content_MD5 = base64.b64encode(hashlib.md5(Body.encode("utf-8")).digest()).decode(
        "utf-8"
    )
    encryptStr = (
        VERB
        + "\n"
        + Content_MD5
        + "\n"
        + Content_Type
        + "\n"
        + Date
        + "\n"
        + CanonicalizedResource
    )
    h = hmac.new(
        solisInfo["solisSecret"], msg=encryptStr.encode("utf-8"), digestmod=hashlib.sha1
    )
    Sign = base64.b64encode(h.digest())
    Authorization = "API " + solisInfo["solisKey"] + ":" + Sign.decode("utf-8")
    requestStr = (
        VERB
        + " "
        + CanonicalizedResource
        + "\n"
        + "Content-MD5: "
        + Content_MD5
        + "\n"
        + "Content-Type: "
        + Content_Type
        + "\n"
        + "Date: "
        + Date
        + "\n"
        + "Authorization: "
        + Authorization
        + "\n"
        + "Body："
        + Body
    )
    header = {
        "Content-MD5": Content_MD5,
        "Content-Type": Content_Type,
        "Date": Date,
        "Authorization": Authorization,
    }

    status_code = 0
    retry_count = 0

    while status_code != 200 and retry_count < 10:
        try:
            resp = Session.post(req, data=Body, headers=header, timeout=60)
            status_code = resp.status_code
            print("Response status code: " + str(status_code))
            print("Here is the resultant")
            print(json.dumps(resp.json()))
            print("#####################")
            solar_usage = jmespath.search(jmespathfilter, resp.json())
        except Exception as e:
            print("getting the API didn't work sorry - here's why: " + str(e))
        if status_code != 200:
            retry_count = retry_count + 1
            time.sleep(10)
            print("Retrying for attempt " + str(retry_count))

    return solar_usage


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


def write_csv_file(csv_filename_prefix, date_query, solar_usage):
    outstring = ""
    csv_filename = csv_filename_prefix + date_query[0:7] + ".csv"
    # Do something if the file doesn't exist
    if not Path(csv_filename).exists():
        filemode = "wt"
        print("No file found - creating one")
        outstring = "date,"
        for key, value in solar_usage.items():
            outstring = outstring + key + ","
        outstring = outstring[:-1] + "\n"
    else:
        filemode = "a+"

    outstring = outstring + date_query + ","
    for key, value in solar_usage.items():
        outstring = outstring + str(value) + ","
    outstring = outstring[:-1] + "\n"
    csv_file = open(csv_filename, filemode)
    csv_file.write(outstring)
    csv_file.close()


def send_telegram_message(bot, mychatid, date_query, solar_usage):
    outstring = "Data for " + date_query + ":\n"
    for key, value in solar_usage.items():
        outstring = outstring + key + ": " + str(value) + "\n"
    outstring = outstring + "\n\n"
    for key, value in solar_usage.items():
        outstring = outstring + str(value) + ","
    outstring = outstring[:-1] + "\n"
    try:
        sendmessage(bot, mychatid, outstring)
    except Exception as e:
        print("Telegram failed. Sad. Here's why: " + str(e))


def update_solarDay_database(dbInfo, date_query, solar_usage):
    # Timestamp swappage for database funtimes
    solar_usage["year"] = int(date_query.split("-")[0])
    solar_usage["month"] = int(date_query.split("-")[1])
    solar_usage["day"] = int(date_query.split("-")[2])

    # And now we database the data
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
        print("Connecting to the database didn't work sorry. Because this: " + str(e))

    table = dbInfo["dbtable"]
    placeholders = ", ".join(["%s"] * len(solar_usage))
    columns = ", ".join(solar_usage.keys())
    sql = "REPLACE INTO %s ( %s ) VALUES ( %s )" % (table, columns, placeholders)
    try:
        cursor = cnx.cursor()
        cursor.execute(sql, list(solar_usage.values()))
        cnx.commit()
        cursor.close()
        cnx.close()
    except Exception as e:
        print("The insert didn't work. Here's why: " + str(e))


def update_octopus_usage(dbInfo, octopusInfo, date_query):
    print(f"Processing Octopus agile usage data for {date_query}")
    table = octopusInfo["InTable"]

    price_data = get_price_data(octopusInfo, date_query)
    consumed_data = get_consumed_data(octopusInfo, date_query)
    if "results" not in price_data or "results" not in consumed_data:
        if "results" not in price_data:
            print("No results in price_data - please try again later")
        if "results" not in consumed_data:
            print("No results in consumed_data - please try again later")
    else:
        db_ready = False
        try:
            cnx = mysql.connector.connect(
                user=dbInfo["dbuser"],
                password=dbInfo["dbpass"],
                host=dbInfo["dbhost"],
                port=dbInfo["dbport"],
                database=dbInfo["dbname"],
                auth_plugin="mysql_native_password",
            )
            db_ready = True
        except Exception as e:
            print("DB connection didn't work sorry because " + str(e))

        if db_ready:
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


def main():
    # solis info
    solisInfo = {
        "solisUrl": os.environ.get("solisUrl"),
        "solisPath": os.environ.get("solisDayPath"),
        "solisKey": os.environ.get("solisKey"),
        "solisId": os.environ.get("solisId"),
        "solisSn": os.environ.get("solisSn"),
        "solisSecret": bytes(os.environ.get("solisSecret"), "utf-8"),
    }

    # Bot business
    bot = telegram.Bot(token=os.environ.get("telegramBotToken"))
    mychatid = os.environ.get("telegramChatId")

    # Database credentials for the conkers
    dbInfo = {
        "dbuser": os.environ.get("dbUser"),
        "dbpass": os.environ.get("dbPass"),
        "dbhost": os.environ.get("dbHost"),
        "dbname": os.environ.get("dbName"),
        "dbport": os.environ.get("dbPort"),
        "dbtable": os.environ.get("dbDayTable"),
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

    # text output file
    csv_filename_prefix = "/media/dave/james/data/solar-"

    if len(sys.argv) < 2:
        print("Usage: getday.py yyyy-mm-dd")
        print("eg. getday.py 2023-01-15")
        exit(1)
    date_query = sys.argv[1]

    # get the solar data
    solar_usage = get_solis_data(solisInfo, date_query)

    # Send the message
    send_telegram_message(bot, mychatid, date_query, solar_usage)

    # Update solarDay database table
    update_solarDay_database(dbInfo, date_query, solar_usage)

    # do the Octopus stuff
    update_octopus_usage(dbInfo, octopusInfo, date_query)

    # write the csv file
    write_csv_file(csv_filename_prefix, date_query, solar_usage)


if __name__ == "__main__":
    main()
