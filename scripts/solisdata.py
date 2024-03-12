#!/usr/bin/python3
# This needs the following environment variables to be created:
#
#
# export solisURL="https://www.soliscloud.com:13333"
# export solisPath="/v1/api/inverterDetail"

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
# export dbName="YOUR_DB_NAME" # if you use the schema in solar.sql it will be solar
# export dbTable="YOUR_DB_TABLE" # if you use the schema in solar.sql it will be solar5
# export dbPort="YOUR_DB_PORT" # normally 3306

import os
import sys
import json
from calendar import monthrange
import hashlib
from hashlib import sha1
import hmac
import base64
from datetime import datetime
from datetime import timezone
import requests
import time
import jmespath
from pathlib import Path

# needs to be: python-telegram-bot<=13
# urllib3==1.26.15
# requests-toolbelt==0.10.1
import telegram

# important - needs to run pip3 install mysql-connector-python
import mysql.connector


# Push message doings
def sendmessage(bot, chat_id, thisMessage):
    bot.send_message(chat_id=chat_id, text=thisMessage)


# Local time doings
def localtime(inputTime):
    return time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime(inputTime))


def sendTelegram(solar_usage, solar_last, bot, mychatid):
    # Battery Percentage is 100
    if solar_usage["batteryPer"] == 100 and solar_last["batteryPer"] < 100:
        try:
            sendmessage(bot, mychatid, "Solar: Battery is 100%")
        except Exception as e:
            print("Battery 100% didn't work sorry because this: " + str(e))

    # Battery Percentage is less than 20
    if solar_usage["batteryPer"] < 20 and solar_last["batteryPer"] >= 20:
        try:
            sendmessage(bot, mychatid, "Solar: Battery has gone under 20%")
        except Exception as e:
            print("Battery < 20% didn't work sorry because this: " + str(e))

    # Solar In is over 2.5kW
    if solar_usage["solarIn"] >= 2.5 and solar_last["solarIn"] < 2.5:
        try:
            sendmessage(bot, mychatid, "Solar: Incoming in has gone over 2.5kW")
        except Exception as e:
            print("Incoming > 2.5kW didn't work sorry because this: " + str(e))


def getSolis(solisInfo, jmespathfilter):
    solar_usage = {}

    url = solisInfo["solisUrl"]
    CanonicalizedResource = solisInfo["solisPath"]

    req = url + CanonicalizedResource
    VERB = "POST"
    Content_Type = "application/json"
    Session = requests.Session()

    now = datetime.now(timezone.utc)
    Date = now.strftime("%a, %d %b %Y %H:%M:%S GMT")

    # Here's the bit where we get data from Solis
    Body = (
        '{"pageSize":100,  "id": "'
        + solisInfo["solisId"]
        + '", "sn": "'
        + solisInfo["solisSn"]
        + '" }'
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

    # Make the call
    try:
        resp = Session.post(req, data=Body, headers=header, timeout=60)
        solar_usage = jmespath.search(jmespathfilter, resp.json())
    except Exception as e:
        print("get solar_usage didn't work sorry because this: " + str(e))

    if "timestamp" in solar_usage:
        solar_usage["year"] = time.strftime(
            "%Y", time.gmtime(int(int(solar_usage["timestamp"]) / 1000))
        )
        solar_usage["month"] = time.strftime(
            "%m", time.gmtime(int(int(solar_usage["timestamp"]) / 1000))
        )
        solar_usage["day"] = time.strftime(
            "%d", time.gmtime(int(int(solar_usage["timestamp"]) / 1000))
        )
        solar_usage["hour"] = time.strftime(
            "%H", time.gmtime(int(int(solar_usage["timestamp"]) / 1000))
        )
        solar_usage["minute"] = time.strftime(
            "%M", time.gmtime(int(int(solar_usage["timestamp"]) / 1000))
        )
        solar_usage["timestamp"] = time.strftime(
            "%Y%m%d%H%M", time.gmtime(int(int(solar_usage["timestamp"]) / 1000))
        )
    else:
        solar_usage["year"] = time.strftime("%Y", time.gmtime(int(time.time())))
        solar_usage["month"] = time.strftime("%m", time.gmtime(int(time.time())))
        solar_usage["day"] = time.strftime("%d", time.gmtime(int(time.time())))
        solar_usage["hour"] = time.strftime("%H", time.gmtime(int(time.time())))
        solar_usage["minute"] = time.strftime("%M", time.gmtime(int(time.time())))
        solar_usage["timestamp"] = time.strftime(
            "%Y%m%d%H%M", time.gmtime(int(time.time()))
        )

    return solar_usage


# Doing stuff for the local file


def localFile(solar_usage, latestFileName):
    latest = {}
    latest["solar"] = solar_usage["solarIn"]
    latest["battery"] = solar_usage["batteryPer"]
    latest["grid"] = solar_usage["gridIn"]
    latest["usage"] = solar_usage["powerUsed"]
    latest["timestamp"] = solar_usage["timestamp"]

    f = open(latestFileName, "w")
    f.write(json.dumps(latest))
    f.close()


def main():

    # solis info
    solisInfo = {
        "solisUrl": os.environ.get("solisUrl"),
        "solisPath": os.environ.get("solisPath"),
        "solisKey": os.environ.get("solisKey"),
        "solisSecret": bytes(os.environ.get("solisSecret"), "utf-8"),
        "solisId": os.environ.get("solisId"),
        "solisSn": os.environ.get("solisSn"),
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
        "dbtable": os.environ.get("dbTable"),
    }

    # jmespath filter
    jmespathfilter = "data.{ \
                    timestamp:dataTimestamp, \
                    powerUsed:familyLoadPower, \
                    gridIn: psum, \
                    solarIn: pac, \
                    batteryIn: batteryPower, \
                    batteryPer: batteryCapacitySoc, \
                    solarInToday: eToday, \
                    gridInToday: gridPurchasedTodayEnergy, \
                    gridOutToday: gridSellTodayEnergy }"

    # Local file for the silly little display thingy
    latestFileName = "/usr/local/www/html/solar/latest.json"

    solar_usage = getSolis(solisInfo, jmespathfilter)

    print("solis timestamp is: " + solar_usage["timestamp"])

    # database bits

    try:
        cnx = mysql.connector.connect(
            user=dbInfo["dbuser"],
            password=dbInfo["dbpass"],
            host=dbInfo["dbhost"],
            port=dbInfo["dbport"],
            database=dbInfo["dbname"],
            auth_plugin="mysql_native_password",
            connect_timeout=20,
        )
    except Exception as e:
        print("DB select didn't work sorry because " + str(e))

    table = dbInfo["dbtable"]

    # Get the latest stuff
    cursor = cnx.cursor()
    sql = "select year,month,day,hour,minute,powerUsed, gridIn, solarIn, batteryIn, batteryPer from solar5 order by updated_timstm desc limit 1;"
    cursor.execute(sql)
    data = cursor.fetchone()
    cursor.close()
    solar_last = {}
    (
        solar_last["year"],
        solar_last["month"],
        solar_last["day"],
        solar_last["hour"],
        solar_last["minute"],
        solar_last["powerUsed"],
        solar_last["gridIn"],
        solar_last["solarIn"],
        solar_last["batteryIn"],
        solar_last["batteryPer"],
    ) = [data[i] for i in (range(len(data)))]

    latest_timestamp = f"{solar_last['year']:04d}{solar_last['month']:02d}{solar_last['day']:02d}{solar_last['hour']:02d}{solar_last['minute']:02d}"
    print("latest_timestamp is: " + latest_timestamp)

    # Only need to run this bit if the data is different - means we can run it every minute
    if latest_timestamp != solar_usage["timestamp"]:
        print("Thems is different so let's go")

        # Send some telegram messages if you like
        sendTelegram(solar_usage, solar_last, bot, mychatid)

        # Update the new stuff

        solar_db = solar_usage.copy()
        del solar_db["timestamp"]
        placeholders = ", ".join(["%s"] * len(solar_db))
        columns = ", ".join(solar_db.keys())
        sql = "INSERT INTO %s ( %s ) VALUES ( %s )" % (table, columns, placeholders)
        try:
            cursor = cnx.cursor()
            cursor.execute(sql, list(solar_db.values()))
            cnx.commit()
            cursor.close()
            cnx.close()
        except Exception as e:
            print("DB insert didn't work sorry because this: " + str(e))

        # There is no local file
        # localFile(solar_usage, latestFileName)


if __name__ == "__main__":
    main()
