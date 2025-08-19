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
import json
from calendar import monthrange
from hashlib import sha1,md5
import hmac
import base64
from datetime import datetime
from datetime import timezone
import requests
import time
import jmespath
from pathlib import Path
from gspread_formatting import numberFormat


# Google doings
from include.google_sheets import Spreadsheet

# Main variables doings 
#######################
# Local file for the silly little display thingy
latest_json_file="/usr/local/www/html/solar/latest.json"

# Max lines in the solar5 spreadsheet to keep the numbers down
max_lines=10000

# Local file for CSV backup
solar_csv_file=f'/media/solar/solar5/solar5_{datetime.now().strftime("%Y-%m-%d")}.csv'

current_path=os.path.dirname(os.path.abspath(__file__))


# Local time doings
def localtime(inputTime):
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(inputTime))

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
  Content_MD5 = base64.b64encode(md5(Body.encode('utf-8')).digest()).decode('utf-8')
  encryptStr = (f"{VERB}\n{Content_MD5}\n{Content_Type}\n{Date}\n{CanonicalizedResource}")
  h = hmac.new(solisInfo['solisSecret'], msg=encryptStr.encode('utf-8'), digestmod=sha1)
  Sign = base64.b64encode(h.digest())
  Authorization = "API " + solisInfo['solisKey'] + ":" + Sign.decode('utf-8')
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

def write_latest_file(solar_usage,latestFileName):
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


# Initialize spreadsheet
  sheet = Spreadsheet(
    creds_file=f"{current_path}/../google.json",
    spreadsheet_name="Solar Database",
    worksheet_name="solar5",
  )

# Then get the solis data yeah
  solar_usage=getSolis(solisInfo,jmespathfilter)

# Using timestamp as the success factor because why not
  
  if "timestamp" in solar_usage:
    print("solis timestamp is: "+solar_usage['timestamp'])
    
    # Get the latest stuff from the latest_worksheet - complicated really
    last_row=sheet.get_last_row(sheet.worksheet)
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
      # solar_usage['datetime_string']=f"{solar_usage['year']:04d}-{solar_usage['month']:02d}-{solar_usage['day']:02d} {solar_usage['hour']:02d}{solar_usage['minute']:02d}"
      solar_usage['datetime_string']=f"{solar_usage['year']}-{solar_usage['month']}-{solar_usage['day']} {solar_usage['hour']}:{solar_usage['minute']}:00"
      keys=['year','month','day','hour','minute','datetime_string','powerUsed','gridIn','solarIn','batteryIn','batteryPer','solarInToday','gridInToday','gridOutToday']
      for key in keys:
        new_row_data.append(solar_usage[key])
      new_row_data.append(localtime(time.time()))

# Update the new stuff
      sheet.worksheet.append_row(new_row_data)

      column_formats = {
          'A:E': numberFormat(type='NUMBER', pattern='0'),
          'F:F': numberFormat(type='DATE_TIME', pattern='yyyy-mm-dd hh:mm'),
          'G:J': numberFormat(type='NUMBER', pattern='0.000'),
          'K:K': numberFormat(type='NUMBER', pattern='0'),
          'L:L': numberFormat(type='NUMBER', pattern='0.0'),
          'M:N': numberFormat(type='NUMBER', pattern='0.00'),
          'O:O': numberFormat(type='DATE_TIME', pattern='yyyy-mm-dd hh:mm:ss')
      }
      sheet.format_and_fix_numbers(sheet.worksheet,column_formats)

      sheet.trim_rows(max_rows)

  # Append to the solar csv file
      if not os.path.exists(solar_csv_file):
        with open(solar_csv_file, 'w') as f:
          f.write(f'{(",").join(x for x in keys)}\n')
        f.close
      with open(solar_csv_file, "a") as f:
        f.write(f'{",".join(str(x) for x in new_row_data)}\n')
      f.close()

      
  # Do the local latest file
      write_latest_file(solar_usage,latest_json_file)
  else:
    print("Nothing back from Solis this time - sorry.")
  
if __name__ == "__main__":
  main()
