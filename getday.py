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

import logging

# Create a logger
logger = logging.getLogger("")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


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


# Push message doings
def sendmessage(bot, chat_id, thisMessage):
    logger.debug(f"in sendmessage function - chat_id is {chat_id}")
    bot.send_message(chat_id=chat_id, text=thisMessage)


def localtime(inputTime):
    logger.debug(f"in localtime function - inputTime is {inputTime}")
    return time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime(inputTime))


# Local time doings
def utc_calc(time_string, day_diff=0):
    logger.debug(f"in utc_calc - time_string is {time_string} - day_diff is {day_diff}")
    local = pytz.timezone("Europe/London")
    naive = datetime.strptime(time_string, "%Y-%m-%d")
    local_dt = local.localize(naive, is_dst=None)
    utc_dt = local_dt.astimezone(pytz.utc) + timedelta(days=day_diff)
    logger.debug(f"End of utc_calc")
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def get_solis_data(solisInfo, date_query):
    logger.info(f"running get_solis_data function for {date_query}")
    # jmespath filter
    jmespathfilter = "data.records[0].{totalConsumed:consumeEnergy, solarGen:energy, solarExport:gridSellEnergy, batCharge:batteryChargeEnergy, selfUse:oneSelf, gridImport:gridPurchasedEnergy, batUse:batteryDischargeEnergy}"
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
        logger.debug(f"into the request loop - retry count is {retry_count}")
        try:
            resp = Session.post(req, data=Body, headers=header, timeout=60)
            status_code = resp.status_code
            logger.info(f"Response status code: {str(status_code)}")
            logger.debug("\nHere is the resultant solis doings")
            logger.debug(json.dumps(resp.json()))
            logger.debug("\n##################################\n")
            solar_usage = jmespath.search(jmespathfilter, resp.json())
        except Exception as e:
            logger.error(f"getting the API didn't work sorry - here's why: {str(e)}")
        if status_code != 200:
            retry_count = retry_count + 1
            time.sleep(10)
            logger.info("Retrying for attempt " + str(retry_count))
    logger.debug(f"End of get_solis_data")
    return solar_usage


def write_csv_file(csv_filename_prefix, date_query, solar_usage):
    if solar_usage:
        logger.info(f"running write_csv_file function for {date_query}")
        outstring = ""
        csv_filename = csv_filename_prefix + date_query[0:7] + ".csv"
        logger.info(f"preparing to write {csv_filename} file")

        # Do something if the file doesn't exist
        if not Path(csv_filename).exists():
            filemode = "wt"
            logger.warning("No file found - creating one")
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
    else:
        logger.debug("No solar_usage data - skipping to the end of write_csv_file")
    logger.debug(f"End of write_csv_file")


def send_telegram_message(bot, mychatid, date_query, solar_usage):
    logger.info(f"running send_telegram_message for {date_query}")
    if solar_usage:
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
            logger.error("Telegram failed. Sad. Here's why: " + str(e))
    else:
        logger.debug(
            "No solar_usage data - skipping to the end of send_telegram_message"
        )
    logger.debug(f"End of send_telegram_message")


def update_solarDay_database(dbInfo, date_query, solar_usage):
    logger.info(f"running update_solarDay_database function for {date_query}")
    if solar_usage:
        new_data = False
        db_ready = False
        # Timestamp swappage for database funtimes
        solar_usage["year"] = int(date_query.split("-")[0])
        solar_usage["month"] = int(date_query.split("-")[1])
        solar_usage["day"] = int(date_query.split("-")[2])

        logger.debug(
            f"making the DB connection to {dbInfo['dbname']} on {dbInfo['dbhost']}"
        )
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
            db_ready = True
        except Exception as e:
            logger.error(
                f"Connecting to the database didn't work sorry. Because this: {str(e)}"
            )
        if db_ready:
            table = dbInfo["dbtable"]

            # Check to see if there's data there already - avoid duplicating messages
        if db_ready:
            # check to see if there's already data
            logger.debug(f"Checking to see if there's already data for {date_query}")

            sql = (
                "select count(totalConsumed) as `QTY` from %s where year= %s and month = %s and day = %s"
                % (
                    table,
                    int(date_query[:4]),
                    int(date_query[5:7]),
                    int(date_query[8:10]),
                )
            )
            cursor = cnx.cursor()
            try:
                cursor.execute(sql)
                for (QTY,) in cursor:
                    if int(QTY) == 0:
                        new_data = True
            except Exception as e:
                logger.error(
                    f"current data select query didn't work sorry because {str(e)}"
                )
            cursor.close()

            # do the DB bit
            logger.debug(f"Building the REPLACE INTO query for {date_query}")
            placeholders = ", ".join(["%s"] * len(solar_usage))
            columns = ", ".join(solar_usage.keys())
            sql = "REPLACE INTO %s ( %s ) VALUES ( %s )" % (
                table,
                columns,
                placeholders,
            )
            logger.debug(f"running the REPLACE INTO sql on {dbInfo['dbtable']}")
            try:
                cursor = cnx.cursor()
                cursor.execute(sql, list(solar_usage.values()))
                cnx.commit()
                cursor.close()
                cnx.close()
            except Exception as e:
                logger.error(f"The REPLACE INTO didn't work. Here's why: {str(e)}")
    else:
        logger.debug(
            "No solar_usage data - skipping to the end of update_solarDay_database"
        )

    logger.debug(f"End of update_solarDay_database")
    return new_data


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

    # text output file
    csv_filename_prefix = "/media/dave/james/data/solar-"

    if len(sys.argv) < 2:
        print("Usage: getday.py yyyy-mm-dd")
        print("eg. getday.py 2023-01-15")
        exit(1)
    date_query = sys.argv[1]

    # get the solar data
    solar_usage = get_solis_data(solisInfo, date_query)

    # update the database
    new_data = update_solarDay_database(dbInfo, date_query, solar_usage)

    if new_data:
        logger.debug("New data - so update the csv and send the telegram message")
        # Send the message
        send_telegram_message(bot, mychatid, date_query, solar_usage)

        # write the csv file
        write_csv_file(csv_filename_prefix, date_query, solar_usage)
    else:
        logger.debug(
            "Data already in the DB - no need to update the csv and send the telegram message"
        )


if __name__ == "__main__":
    main()
