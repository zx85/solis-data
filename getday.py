#!/usr/bin/python3
import os
import sys
import json
from calendar import monthrange
from hashlib import sha1,md5
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

# Google doings
from include.googlesheets import Spreadsheet
 
# logging
from include.logger import log

# Super necessary variable definitions
current_path=os.path.dirname(os.path.abspath(__file__))
creds_file=f'{current_path}/google.json'

# text output file
csv_filename_prefix = "/media/dave/james/data/solar/solarDay/solarDay_"


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

# Push message doings
def sendmessage(bot, chat_id, thisMessage):
    log.debug(f"in sendmessage function - chat_id is {chat_id}")
    bot.send_message(chat_id=chat_id, text=thisMessage)


def localtime(inputTime):
    log.debug(f"in localtime function - inputTime is {inputTime}")
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(inputTime))


# Local time doings
def utc_calc(time_string, day_diff=0):
    log.debug(f"in utc_calc - time_string is {time_string} - day_diff is {day_diff}")
    local = pytz.timezone("Europe/London")
    naive = datetime.strptime(time_string, "%Y-%m-%d")
    local_dt = local.localize(naive, is_dst=None)
    utc_dt = local_dt.astimezone(pytz.utc) + timedelta(days=day_diff)
    log.debug(f"End of utc_calc")
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def get_solis_data(solisInfo, date_query):
    log.info(f"running get_solis_data function for {date_query}")
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
        f'{{'
        f'"time":"{date_query}", '
        f'"pageSize":100, '
        f'"sn":"{solisInfo["solisSn"]}", '
        f'"id":"{solisInfo["solisId"]}"'
        f'}}'
    )
    Content_MD5 = base64.b64encode(md5(Body.encode("utf-8")).digest()).decode(
        "utf-8"
    )
    encryptStr = f"{VERB}\n{Content_MD5}\n{Content_Type}\n{Date}\n{CanonicalizedResource}"
    h = hmac.new(
        solisInfo["solisSecret"], msg=encryptStr.encode("utf-8"), digestmod=sha1
    )
    Sign = base64.b64encode(h.digest())
    Authorization = "API " + solisInfo["solisKey"] + ":" + Sign.decode("utf-8")
    header = {
        "Content-MD5": Content_MD5,
        "Content-Type": Content_Type,
        "Date": Date,
        "Authorization": Authorization,
    }

    status_code = 0
    retry_count = 0
    while status_code != 200 and retry_count < 10:
        log.debug(f"into the request loop - retry count is {retry_count}")
        try:
            resp = Session.post(req, data=Body, headers=header, timeout=60)
            status_code = resp.status_code
            log.info(f"Response status code: {str(status_code)}")
            log.debug("\nHere is the resultant solis doings")
            log.debug(json.dumps(resp.json()))
            log.debug("\n##################################\n")
            solar_usage = jmespath.search(jmespathfilter, resp.json())
        except Exception as e:
            log.error(f"getting the API didn't work sorry - here's why: {str(e)}")
        if status_code != 200:
            retry_count = retry_count + 1
            time.sleep(10)
            log.info("Retrying for attempt " + str(retry_count))
    log.debug(f"End of get_solis_data")
    return solar_usage


def write_csv_file(csv_filename_prefix, date_query, solar_usage):
    if solar_usage:
        log.info(f"running write_csv_file function for {date_query}")
        outstring = ""
        csv_filename = csv_filename_prefix + date_query[0:7] + ".csv"
        log.info(f"preparing to write {csv_filename} file")

        # Do something if the file doesn't exist
        if not Path(csv_filename).exists():
            filemode = "wt"
            log.warning("No file found - creating one")
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
        log.debug("No solar_usage data - skipping to the end of write_csv_file")
    log.debug(f"End of write_csv_file")


def send_telegram_message(bot, mychatid, date_query, solar_usage):
    log.info(f"running send_telegram_message for {date_query}")
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
            log.error("Telegram failed. Sad. Here's why: " + str(e))
    else:
        log.debug(
            "No solar_usage data - skipping to the end of send_telegram_message"
        )
    log.debug(f"End of send_telegram_message")


def update_solarDay_database(sheet,date_query, solar_usage):
    new_data = False
    log.info(f"running update_solarDay_database function for {date_query}")
    if solar_usage:
        # Timestamp swappage for database funtimes
        solar_usage["year"] = int(date_query.split("-")[0])
        solar_usage["month"] = int(date_query.split("-")[1])
        solar_usage["day"] = int(date_query.split("-")[2])
        sheet_query=[solar_usage["year"],solar_usage["month"],solar_usage["day"]]
        # Check to see if there's an entry already
        if not (sheet.check_values_in_columns(sheet_query)):
            log.info('Need to add this one yeah')
            new_data = True
            field_list=["year",
                        "month",
                        "day",
                        "totalConsumed",
                        "solarGen",
                        "solarExport",
                        "batCharge",
                        "selfUse",
                        "gridImport",
                        "batUse"]
            new_row_data=[]
            for field in field_list:
                new_row_data.append(solar_usage[field])
            new_row_data.append(localtime(time.time()))
            sheet.worksheet.append_row(new_row_data)
            # Then copy the formula from the previous rows
            copy_cols=['L','M']
            sheet.copy_formulas_for_columns(copy_cols)
    else:
        log.debug(
            "No solar_usage data - skipping to the end of update_solarDay_database"
        )
    log.debug(f"End of update_solarDay_database")
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

    # Google Sheets goodies
# Initialize spreadsheet
    sheet = Spreadsheet(
        creds_file=creds_file,
        spreadsheet_name="Solar Database",
        worksheet_name="solarDay",
    )


    if len(sys.argv) < 2:
        print("Usage: getday.py yyyy-mm-dd")
        print("eg. getday.py 2023-01-15")
        exit(1)
    date_query = sys.argv[1]

    # get the solar data
    solar_usage = get_solis_data(solisInfo, date_query)

    # update the database
    if update_solarDay_database(sheet, date_query, solar_usage):
        log.debug("New data - so update the csv and send the telegram message")
        # Send the message
        send_telegram_message(bot, mychatid, date_query, solar_usage)

        # write the csv file
        write_csv_file(csv_filename_prefix, date_query, solar_usage)
    else:
        log.debug(
            "Data already in the DB - no need to update the csv and send the telegram message"
        )


if __name__ == "__main__":
    main()
