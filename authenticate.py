import requests
import time
import json

# Configuration
REGION_CONFIG = {
    'world': {
        'url_mini': 'https://ayla-sso.owletdata.com/mini/',
        'url_signin': 'https://user-field-1a2039d9.aylanetworks.com/api/v1/token_sign_in',
        'url_base': 'https://ads-field-1a2039d9.aylanetworks.com/apiv1',
        'apiKey': 'AIzaSyCsDZ8kWxQuLJAMVnmEhEkayH1TSxKXfGA',
        'databaseURL': 'https://owletcare-prod.firebaseio.com',
        'storage_bucket': 'owletcare-prod.appspot.com',
        'app_id': 'sso-prod-3g-id',
        'app_secret': 'sso-prod-UEjtnPCtFfjdwIwxqnC0OipxRFU',
    },
    'europe': {
        'url_mini': 'https://ayla-sso.eu.owletdata.com/mini/',
        'url_signin': 'https://user-field-eu-1a2039d9.aylanetworks.com/api/v1/token_sign_in',
        'url_base': 'https://ads-field-eu-1a2039d9.aylanetworks.com/apiv1',
        'apiKey': 'AIzaSyDm6EhV70wudwN3iOSq3vTjtsdGjdFLuuM',
        'databaseURL': 'https://owletcare-prod-eu.firebaseio.com',
        'storage_bucket': 'owletcare-prod-eu.appspot.com',
        'app_id': 'OwletCare-Android-EU-fw-id',
        'app_secret': 'OwletCare-Android-EU-JKupMPBoj_Npce_9a95Pc8Qo0Mw',
    }
}

def get_auth_token(owlet_user, owlet_pass, headers={}, auth_token=None, expire_time=0, owlet_region='world'):
    '''Login using the Owlet account credentials to get API token.

    Args:
        owlet_user: Username for Owlet account (email)
        owlet_pass: Password for Owlet account
        headers: Dictionary of any specific headers beyond defaults
        auth_token: Specifying old token will check expiration
        expire_time: Specifying a timestamp when token should expire
        owlet_region: Region for default credentials (Europe is different)

    Returns:
        Dictionary of 'token' and the `expiration` timestamp for token.
    '''
    # Check if token already exists and hasn't expired
    if auth_token is not None and (expire_time > time.time()):
        token = {
            'token': auth_token,
            'expiration': expire_time,
            'creation':time.time()
        }
        headers['Authorization'] = 'auth_token ' + auth_token
        return token
    # DEBUG
    print('Authenticating with login information...')

    # Authenticate against Firebase, get the JWT
    config = {
            "apiKey": REGION_CONFIG[owlet_region]['apiKey'],
            "databaseURL": REGION_CONFIG[owlet_region]['databaseURL'],
            "storageBucket": REGION_CONFIG[owlet_region]['storage_bucket'],
            "authDomain": None,
    }

    ## UPDATES: Use new process (not Firebase) 
    # see https://github.com/mbevand/owlet_monitor/commit/34c0703b7811143f7d7bf89a4a6189f1d071ea4f
    r = requests.post(
            f'https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key={config["apiKey"]}',
            data=json.dumps({'email': owlet_user, 'password': owlet_pass, 'returnSecureToken': True}),
            headers={
                'X-Android-Package': 'com.owletcare.owletcare',
                'X-Android-Cert': '2A3BC26DB0B8B0792DBE28E6FFDC2598F9B12B74'
            }
    )
    r.raise_for_status()
    jwt = r.json()['idToken']

    # Authenticate against owletdata.com, get the mini_token
    r = requests.get(
        REGION_CONFIG[owlet_region]['url_mini'], 
        headers={'Authorization': jwt}
    )
    r.raise_for_status()
    mini_token = r.json()['mini_token']

    # Authenticate against Ayla, get the access_token
    r = requests.post(
        REGION_CONFIG[owlet_region]['url_signin'], 
        json={
                "app_id": REGION_CONFIG[owlet_region]['app_id'],
                "app_secret": REGION_CONFIG[owlet_region]['app_secret'],
                "provider": "owl_id",
                "token": mini_token
        }
    )
    r.raise_for_status()

    auth_token = r.json()['access_token']
    # Re-authenticate in the future (has been every 24 hours)
    expire_time = time.time() + r.json()['expires_in']
    headers['Authorization'] = 'auth_token ' + auth_token

    # DEBUG
    print(f'Token: {auth_token}')
    print(f'Expires: {expire_time}')

    token = {
        'token': auth_token,
        'expiration': expire_time,
        'creation':time.time()
    }
    return token