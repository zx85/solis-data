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
import re
import logging
from http import HTTPStatus
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

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

LOGIN_URL = '/v2/api/login'
CONTROL_URL= '/v2/api/control'
READ_COMMAND_URL= '/v2/api/atReadCommand'
INVERTER_URL= '/v1/api/inverterList'
CID='130'

def digest(body: str) -> str:
    return base64.b64encode(md5(body.encode('utf-8')).digest()).decode('utf-8')
    
def passwordEncode(password: str) -> str:
    md5Result = md5(password.encode('utf-8')).hexdigest()
    return md5Result


def prepare_header(config: dict[str,str], body: str, canonicalized_resource: str) -> dict[str, str]:
    content_md5 = digest(body)
    content_type = "application/json"
    
    now = datetime.now(timezone.utc)
    date = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
    
    encrypt_str = ("POST" + "\n"
        + content_md5 + "\n"
        + content_type + "\n"
        + date + "\n"
        + canonicalized_resource
    )
    hmac_obj = hmac.new(
        config["solisSecret"].encode('utf-8'),
        msg=encrypt_str.encode('utf-8'),
        digestmod=sha1
    )
    sign = base64.b64encode(hmac_obj.digest())
    authorization = "API " + config["solisKey"] + ":" + sign.decode('utf-8')
    
    header = {
        "Content-MD5":content_md5,
        "Content-Type":content_type,
        "Date":date,
        "Authorization":authorization
    }
    return header

def login_solis(solis_config):
    body = {"userInfo": solis_config['solisUsername'],
            "password": passwordEncode(solis_config['solisPassword'])}
    body_json=json.dumps(body)
    header = prepare_header(solis_config, body_json, LOGIN_URL)
    req=f'{solis_config["solisUrl"]}{LOGIN_URL}'
    session = requests.Session()
    response = session.post(req, data=body_json, headers=header)
    status = response.status_code

    try:
        text = response.text
        # remove trailing commas before parsing JSON
        cleaned = re.sub(r'("(?:\\?.)*?")|,\s*([}\]])', r'\1\2', text)
        r = json.loads(cleaned)
    except Exception:
        r = {}
    if status == HTTPStatus.OK:
        result = r
        token = result.get("csrfToken") or None
        if not token:
            raise RuntimeError(f"Login succeeded but csrfToken missing in response: {response.text}")
        return token
        log.warning("Login failed: %s %s", status, response.text)
        raise RuntimeError(f"Login failed: {status} {response.text}")
    else:
        log.warning(status)
    return None


def get_config(solis_config):
  session = requests.Session()
  # Here's the bit where we get data from Solis
  body = {"pageSize":100,
          "inverterSn": solis_config['solisSn'],
          "cid": CID}
  body_json=json.dumps(body)     
  header = prepare_header(solis_config, body_json, READ_COMMAND_URL)
  req=f'{solis_config["solisUrl"]}{READ_COMMAND_URL}'
  # Make the call
  try:
    resp = session.post(req, data=body_json, headers=header,timeout=60)
    log.info("response code: "+str(resp.status_code))
    log.info(f"response:\n{json.dumps(resp.json(), indent=2)}")
  except Exception as e:
    log.info(f'Oh no - this happened: {e}')

 
def main():

# solis info
  solis_config = {}
  for solis_configs in ['solisUrl','solisKey','solisSecret','solisId','solisSn','solisUsername','solisPassword']:
    solis_config[solis_configs]=os.environ.get(solis_configs)

  log.info('Doing things')
  solis_config['token']=login_solis(solis_config)
  log.info(solis_config)
  config=get_config(solis_config)

if __name__ == "__main__":
  main()
