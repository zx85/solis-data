from hashlib import sha1,md5
import hmac
import base64
from datetime import datetime
from datetime import timezone
import requests
import time
import jmespath

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
    epoch_timestamp=time.gmtime(int(int(solar_usage['timestamp'])/1000))
    solar_usage['year']=(time.strftime('%Y', epoch_timestamp))
    solar_usage['month']=(time.strftime('%m', epoch_timestamp))
    solar_usage['day']=(time.strftime('%d', epoch_timestamp))
    solar_usage['hour']=(time.strftime('%H', epoch_timestamp))
    solar_usage['minute']=(time.strftime('%M', epoch_timestamp))
    solar_usage['timestamp']=(time.strftime('%Y%m%d%H%M', epoch_timestamp))

  return solar_usage
 