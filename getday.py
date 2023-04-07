#!/usr/bin/python3
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


# Push message doings
def sendmessage(bot,chat_id,thisMessage):
    bot.send_message(chat_id=chat_id,text=thisMessage)

def localtime(inputTime):
        return time.strftime('%Y-%m-%d %H:%M:%S %Z', time.localtime(inputTime))

# solis info
solisInfo = {"solisUrl" : os.environ.get('solisUrl'),
             "solisPath" : os.environ.get('solisDayPath'),
             "solisKey" : os.environ.get('solisKey'),
             "solisSecret" : bytes(os.environ.get('solisSecret'),'utf-8') }

# Bot business
bot = telegram.Bot(token=os.environ.get('telegramBotToken'))
mychatid=os.environ.get('telegramChatId')

# Database credentials for the conkers
dbInfo = { "dbuser" : os.environ.get('dbUser'),
           "dbpass" : os.environ.get('dbPass'),
           "dbhost" : os.environ.get('dbHost'),
           "dbname" : os.environ.get('dbName'),
           "dbport" : os.environ.get('dbPort'),
           "dbtable" : os.environ.get('dbDayTable') }


# jmespath filter
jmespathfilter="data.records[0].{totalConsumed:consumeEnergy, solarGen:produceEnergy, solarExport:gridSellEnergy, batCharge:batteryChargeEnergy, selfUse:oneSelf, gridImport:gridPurchasedEnergy, batUse:batteryDischargeEnergy}"

if len(sys.argv)<2:
    print("Usage: getday.py yyyy-mm-dd")
    print("eg. getday.py 2023-01-15")
    exit(1)
date_query = sys.argv[1]
solar_usage={}

url = solisInfo['solisUrl']
CanonicalizedResource = solisInfo['solisPath']
req = url + CanonicalizedResource
VERB="POST"
Content_Type = "application/json"
Session = requests.Session()

now = datetime.now(timezone.utc)
Date = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
Body = '{"time":"' + date_query +'", "pageSize":100}'
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
try:
    resp = Session.post(req, data=Body, headers=header,timeout=60)
    solar_usage = jmespath.search(jmespathfilter,resp.json())
except Exception as e:
    print ("getting the API didn't work sorry - here's why: " + str(e))
    
# output file
csv_filename = "/media/dave/james/data/solar-"+date_query[0:7]+".csv"

outstring=""
# Do something if the file doesn't exist
if not Path(csv_filename).exists():
    filemode="wt"
    print("No file found - creating one")
    outstring="date,"
    for key,value in solar_usage.items():
        outstring=outstring+key+","
    outstring=outstring[:-1]+"\n"
else:
   filemode="a+"

outstring=outstring+date_query+","
for key,value in solar_usage.items():
    outstring=outstring+str(value)+","
outstring=outstring[:-1]+"\n"
csv_file = open(csv_filename,filemode)
csv_file.write(outstring)
csv_file.close()

# Send the message
outstring="Data for "+date_query+":\n"
for key,value in solar_usage.items():
    outstring=outstring+key+": "+str(value)+"\n"
outstring=outstring+"\n\n"
for key,value in solar_usage.items():
    outstring=outstring+str(value)+","
outstring=outstring[:-1]+"\n"
try:
    sendmessage(bot,mychatid,outstring)
except Exception as e:
    print("Telegram failed. Sad. Here's why: "  + str(e))

# Timestamp swappage for database funtimes
solar_usage['year']=int(date_query.split("-")[0])
solar_usage['month']=int(date_query.split("-")[1])
solar_usage['day']=int(date_query.split("-")[2])
print (json.dumps(solar_usage))

# And now we database the data
try:
    cnx = mysql.connector.connect(user=dbInfo['dbuser'], password=dbInfo['dbpass'],
                                  host=dbInfo['dbhost'], port=dbInfo['dbport'],
                                  database=dbInfo['dbname'], auth_plugin='mysql_native_password')
except Exception as e:
    print ("Connecting to the database didn't work sorry. Because this: " + str(e))

table=dbInfo['dbtable']
placeholders = ', '.join(['%s'] * len(solar_usage))
columns = ', '.join(solar_usage.keys())
sql = "INSERT INTO %s ( %s ) VALUES ( %s )" % (table, columns, placeholders)
try:
    cursor=cnx.cursor()
    cursor.execute(sql, list(solar_usage.values()))
    cnx.commit()
    cursor.close()
    cnx.close()
except Exception as e:
    print ("The insert didn't work. Here's why: " + str(e))



