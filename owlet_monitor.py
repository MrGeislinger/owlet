import sys
import os
import time
import requests
import json

# Use custom methods to get authentication token 
import owlet.authenticate as authenticate
import owlet.config as config

# TODO: Check for OWLET_REGION
region_config = config.region_config

class FatalError(Exception):
    pass

def log(log_str):
    '''
    Log string to logfile.
    '''
    sys.stderr.write(f'{log_str}\n')
    sys.stderr.flush()

def record(s):
    '''
    Write data out.
    '''
    sys.stdout.write(s + '\n')
    sys.stdout.flush()

def login(owlet_user, owlet_pass, headers={}, auth_token=None, expire_time=0, owlet_region='world'):
    '''
    Login using the Owlet account credentials to get API credentials.

    Args:
        owlet_user
        owlet_pass
        headers
        auth_token: Authentication from previous function run
        expire_time
        owlet_region

    Returns:
        auth_token
        expire_time
        headers

    '''
    # Use method to get authentication token
    token = authenticate.get_auth_token(
        owlet_user, 
        owlet_pass, 
        headers, 
        auth_token, 
        expire_time, 
        owlet_region
    )

    auth_token = token['token']
    expire_time = token['expiration']
    # TODO: remove side effect
    headers['Authorization'] = 'auth_token ' + auth_token
    log('Auth token %s' % auth_token)

    return auth_token, expire_time, headers

def fetch_dsn(sess, headers, dsn=[], url_props=[], url_activate=[], owlet_region='world'):
    '''
    '''
    if not dsn:
        log('Getting DSN')
        r = sess.get(region_config[owlet_region]
                     ['url_base'] + '/devices.json', headers=headers)
        r.raise_for_status()
        devs = r.json()
        if len(devs) < 1:
            raise FatalError('Found zero Owlet monitors')
        # Allow for multiple devices
        dsn = []
        url_props = []
        url_activate = []
        for device in devs:
            device_sn = device['device']['dsn']
            dsn.append(device_sn)
            log('Found Owlet monitor device serial number %s' % device_sn)
            url_props.append(
                region_config[owlet_region]['url_base'] + '/dsns/' + device_sn
                + '/properties.json'
            )
            url_activate.append(
                region_config[owlet_region]['url_base'] + '/dsns/' + device_sn
                + '/properties/APP_ACTIVE/datapoints.json'
            )
    return dsn, url_activate, url_props

def reactivate(sess, url_activate, headers):
    '''
    '''
    payload = { "datapoint": { "metadata": {}, "value": 1 } }
    r = sess.post(url_activate, json=payload, headers=headers)
    r.raise_for_status()

def fetch_props(sess, headers, dsn, url_activate, url_props):
    '''
    '''
    # Ayla cloud API data is updated only when APP_ACTIVE periodically reset to 1.
    my_props = []
    # Get properties for each device; note no pause between requests for each device
    for device_sn,next_url_activate,next_url_props in zip(dsn,url_activate,url_props):
        reactivate(sess, next_url_activate, headers)
        device_props = {'DSN':device_sn}
        r = sess.get(next_url_props, headers=headers)
        r.raise_for_status()
        props = r.json()
        for prop in props:
            n = prop['property']['name']
            del(prop['property']['name'])
            device_props[n] = prop['property']
        my_props.append(device_props)
    return my_props

def record_vitals(p):
    '''
    '''
    device_sn = p['DSN']
    charge_status = p['CHARGE_STATUS']['value']
    base_station_on = p['BASE_STATION_ON']['value']
    heart = "%d" % p['HEART_RATE']['value']
    oxy = "%d" % p['OXYGEN_LEVEL']['value']
    mov = "wiggling" if p['MOVEMENT']['value'] else "still"
    disp = "%d, " % time.time()
    if charge_status >= 1:
        disp += "sock charging (%d)" % charge_status
        # base_station_on is (always?) 1 in this case
    elif charge_status == 0:
        if base_station_on == 0:
            # sock was unplugged, but user did not turn on the base station.
            # heart and oxygen levels appear to be reported, but we can't
            # yet assume the sock was placed on the baby's foot.
            disp += "sock not charging, base station off"
        elif base_station_on == 1:
            # base station was intentionally turned on, the sock is presumably
            # on the baby's foot, so we can trust heart and oxygen levels
            disp += heart + ", " + oxy + ", " + mov + ", " + device_sn
            record(disp)
        else:
            raise FatalError("Unexpected base_station_on=%d" % base_station_on)
    log("%s Status: " % device_sn + disp)

def loop():
    '''
    '''
    # Check for Owlet credentials defined
    try:
        owlet_user = os.environ['OWLET_USER']
        owlet_pass = os.environ['OWLET_PASS']
        if not len(owlet_user):
            raise FatalError("OWLET_USER is empty")
        if not len(owlet_pass):
            raise FatalError("OWLET_PASS is empty")
    except KeyError as e:
        raise FatalError("OWLET_USER or OWLET_PASS env var is not defined")
    #
    sess = requests.session()
    headers = {}
    # Set defaults for getting authentication
    auth_token = None
    expire_time = 0
    # Set defaults for getting device serial number(s)
    dsn = []
    url_props = []
    url_activate = []
    while True:
        try:
            auth_token, expire_time, headers = login(owlet_user, owlet_pass, headers=headers, auth_token=auth_token, expire_time=expire_time)
            dsn, url_activate, url_props = fetch_dsn(sess, headers, dsn=dsn, url_props=url_props, url_activate=url_activate)
            for prop in fetch_props(sess, headers, dsn, url_activate, url_props):
                record_vitals(prop)
            time.sleep(10)
        except requests.exceptions.RequestException as e:
            log('Network error: %s' % e)
            time.sleep(1)
            sess = requests.session()

def main():
    try:
        loop()
    except FatalError as e:
        sys.stderr.write('%s\n' % e)
        sys.exit(1)

if __name__ == "__main__":
    main()
