#!/usr/bin/python3
# This needs the following environment variables to be created:
# This version doesn't do telegram because I do it with home assistant now
#
# export solisURL="https://www.soliscloud.com:13333"
# export solisPath="/v1/api/inverterDetail"

# export solisKey="YOUR_API_KEY
# export solisSecret="YOUR_API_SECRET"
# export solisId="YOUR_SOLIS_ID"
# export solisSn="YOUR_INVERTER_SERIAL_NUMBER"

# Google credentials in google.json


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

# Google doings
import gspread  # pip install gspread
# Setting up the authorization
from google.oauth2.service_account import Credentials

def convert_types(row):
    def try_number(val):
        try:
            return int(val)
        except ValueError:
            try:
                return float(val)
            except ValueError:
                return val
    return [try_number(cell) for cell in row]


class Spreadsheet:
    def __init__(self, creds_file, spreadsheet_name, worksheet_name,latest_worksheet_name):
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_file(creds_file, scopes=scopes)
        client = gspread.authorize(creds)
        self.spreadsheet = client.open(spreadsheet_name)
        self.worksheet = self.spreadsheet.worksheet(worksheet_name)
        self.latest_worksheet = self.spreadsheet.worksheet(latest_worksheet_name)

    def get_last_row(self,worksheet):
        """Returns the last non-empty row as a list."""
        values = worksheet.get_all_values()
        if values:
            return convert_types(values[-1])
        return []

    def append_row(self,worksheet, row_data):
        """Appends a row to the worksheet."""
        worksheet.append_row(row_data)


    def replace_top_row(self, worksheet, new_row):
        """
        Replaces the first row of the worksheet with the values in new_row.
        """
        # Update the first row with new_row values
        cell_range = f"A1:{gspread.utils.rowcol_to_a1(1, len(new_row))}"
        worksheet.update(values=[new_row],range_name=cell_range)

# Local time doings
def localtime(inputTime):
        return time.strftime('%Y-%m-%d %H:%M:%S %Z', time.localtime(inputTime))


def getSolis(solisInfo,jmespathfilter):
    solar_usage={}

    url = solisInfo['solisUrl']
    CanonicalizedResource = solisInfo['solisPath']

    req = url + CanonicalizedResource
    VERB="POST"
    Content_Type = "application/json"
    Session = requests.Session()
    
    now = datetime.now(timezone.utc)
    Date = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
    
    # Here's the bit where we get data from Solis
    Body = '{"pageSize":100,  "id": "'+solisInfo['solisId']+'", "sn": "'+solisInfo['solisSn']+'" }'
    Content_MD5 = base64.b64encode(hashlib.md5(Body.encode('utf-8')).digest()).decode('utf-8')
    encryptStr = (VERB + "\n"
        + Content_MD5 + "\n"
        + Content_Type + "\n"
        + Date + "\n"
        + CanonicalizedResource)
    h = hmac.new(solisInfo['solisSecret'], msg=encryptStr.encode('utf-8'), digestmod=hashlib.sha1)
    Sign = base64.b64encode(h.digest())
    Authorization = "API " + solisInfo['solisKey'] + ":" + Sign.decode('utf-8')
    requestStr = (VERB + " " + CanonicalizedResource + "\n"
        + "Content-MD5: " + Content_MD5 + "\n"
        + "Content-Type: " + Content_Type + "\n"
        + "Date: " + Date + "\n"
        + "Authorization: "+ Authorization + "\n"
        + "Body：" + Body)
    header = { "Content-MD5":Content_MD5,
                "Content-Type":Content_Type,
                "Date":Date,
                "Authorization":Authorization
                }
    
    # Make the call
    try:
        resp = Session.post(req, data=Body, headers=header,timeout=60)
        print("response code: "+str(resp.status_code))
        solar_usage = jmespath.search(jmespathfilter,resp.json())
    except Exception as e:
        print ("get solar_usage didn't work sorry because this: " + str(e))

    if 'timestamp' in solar_usage:
        solar_usage['year']=(time.strftime('%Y', time.gmtime(int(int(solar_usage['timestamp'])/1000))))
        solar_usage['month']=(time.strftime('%m', time.gmtime(int(int(solar_usage['timestamp'])/1000))))
        solar_usage['day']=(time.strftime('%d', time.gmtime(int(int(solar_usage['timestamp'])/1000))))
        solar_usage['hour']=(time.strftime('%H', time.gmtime(int(int(solar_usage['timestamp'])/1000))))
        solar_usage['minute']=(time.strftime('%M', time.gmtime(int(int(solar_usage['timestamp'])/1000))))
        solar_usage['timestamp']=(time.strftime('%Y%m%d%H%M', time.gmtime(int(int(solar_usage['timestamp'])/1000))))

    return solar_usage
 
# Doing stuff for the local file

def localFile(solar_usage,latestFileName):
    latest={}
    latest['solar']=solar_usage['solarIn']
    latest['battery']=solar_usage['batteryPer']
    latest['grid']=solar_usage['gridIn']
    latest['usage']=solar_usage['powerUsed']
    latest['timestamp']=solar_usage['timestamp']
    
    f = open(latestFileName, "w")
    f.write(json.dumps(latest))
    f.close()

def main():

# solis info
    solisInfo = {"solisUrl" : os.environ.get('solisUrl'),
                 "solisPath" : os.environ.get('solisPath'),
                 "solisKey" : os.environ.get('solisKey'),
                 "solisSecret" : bytes(os.environ.get('solisSecret'),'utf-8'),
                 "solisId" : os.environ.get('solisId'),
                 "solisSn" : os.environ.get('solisSn') }

# jmespath filter
    jmespathfilter="data.{ \
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
    latestFileName="/usr/local/www/html/solar/latest.json"

# Initialize spreadsheet
    sheet = Spreadsheet(
        creds_file="google.json",
        spreadsheet_name="Solar Database",
        worksheet_name="solar5",
        latest_worksheet_name="solar5_latest"
    )

# Then get the solis data yeah
    solar_usage=getSolis(solisInfo,jmespathfilter)

# Using timestamp as the success factor because why not
    
    if "timestamp" in solar_usage:
        print("solis timestamp is: "+solar_usage['timestamp'])
        
        # Get the latest stuff from the latest_worksheet - complicated really
        last_row=sheet.get_last_row(sheet.latest_worksheet)
        print(f'last_row is {last_row}')
        solar_last={}
        solar_last['year'],solar_last['month'],solar_last['day'],solar_last['hour'],solar_last['minute'],solar_last['powerUsed'], solar_last['gridIn'], solar_last['solarIn'], solar_last['batteryIn'], solar_last['batteryPer']=[last_row[i] for i in (range(10))]
        
        latest_timestamp=(f"{solar_last['year']:04d}{solar_last['month']:02d}{solar_last['day']:02d}{solar_last['hour']:02d}{solar_last['minute']:02d}")
        print("latest_timestamp is: "+latest_timestamp)
        

# Only need to run this bit if the data is different - means we can run it every minute
        if latest_timestamp != solar_usage['timestamp']:
            print("Thems is different so let's go")

# Turn the data into a list
            new_row_data=[]
            keys=['year','month','day','hour','minute','powerUsed','gridIn','solarIn','batteryIn','batteryPer','solarInToday','gridInToday','gridOutToday']
            for key in keys:
                new_row_data.append(solar_usage[key])
            new_row_data.append(localtime(time.time()))

# Update the new stuff
            sheet.append_row(sheet.worksheet,new_row_data)
            sheet.replace_top_row(sheet.latest_worksheet,new_row_data)

            
    # Do the local file
            localFile(solar_usage,latestFileName)
    else:
        print("Nothing back from Solis this time - sorry.")
    
if __name__ == "__main__":
    main()
