import webbrowser
from urllib.parse import urlencode
import os
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta
import time

#Requires a developer account and a registered developer app.
#
# Looks for the following environment variables:
#   ENPHASE_API_KEY
#   ENPHASE_CLIENT_ID
#   ENPHASE_CLIENT_SECRET

api_key = os.getenv('ENPHASE_API_KEY')
client_id = os.getenv('ENPHASE_CLIENT_ID')
client_secret = os.getenv('ENPHASE_CLIENT_SECRET')

# Ensure that the environment variables are set
if not api_key or not client_id or not client_secret:
    raise ValueError("Not all ENPHASE API environment variables are set")

def get_env_safe(env_name: str) -> str:
    if env_name is None or len(env_name) == 0:
        raise ValueError(f"The input to this function must be populated!")
    cur_val = os.getenv(env_name)
    if cur_val is None or len(cur_val) == 0:
        raise ValueError(f"Environment variable '{env_name}' is not defined.")
    else:
        return cur_val

def get_initialize_auth_url(redirect_uri: str):
    if redirect_uri is None or len(redirect_uri) == 0:
        raise ValueError(f"redirect_uri input must be populated!")
    
    base_url = 'https://api.enphaseenergy.com/oauth/authorize'
    params = {
        'response_type': 'code',
        'client_id': get_env_safe('ENPHASE_CLIENT_ID'),
        'redirect_uri': redirect_uri
    }

    url = f"{base_url}?{urlencode(params)}"
    return url

def populate_token_dictionary(response_json, token_dictionary: dict):
    token_dictionary['refresh_token'] = response_json['refresh_token']
    token_dictionary['access_token'] = response_json['access_token']
    token_dictionary['access_token_expiration'] = datetime.now() + timedelta(seconds=response_json['expires_in'])
    return token_dictionary

def authorize(code: str, token_dictionary: dict) -> dict:
    base_url = "https://api.enphaseenergy.com/oauth/token" #?grant_type=authorization_code&redirect_uri=https://localhost:5000/enphase_token&code=p1a5HY"
    params = {
        'grant_type': 'authorization_code',
        'redirect_uri': token_dictionary['redirect_uri'],
        'code': code
    }
    url = f"{base_url}?{urlencode(params)}"

    # Make the POST request with basic authorization
    response = requests.post(url, auth=HTTPBasicAuth(client_id, client_secret))

    # Check the response status code and content
    if response.status_code == 200:
        print("Request was successful")
        print("Response content:", response.json())
        return populate_token_dictionary(response.json(), token_dictionary=token_dictionary)
    else:
        print(f"Request failed with status code {response.status_code}")
        print("Response content:", response.text)
        raise ValueError("Unable to authorize!")
    
def refresh_token(token_dictionary: dict) -> dict:
    base_url = "https://api.enphaseenergy.com/oauth/token"
    params = {
        'grant_type': 'refresh_token',
        'refresh_token': token_dictionary['refresh_token']
        }
    url = f"{base_url}?{urlencode(params)}"

    # Make the POST request with basic authorization
    response = requests.post(url, auth=HTTPBasicAuth(client_id, client_secret))

    # Check the response status code and content
    if response.status_code == 200:
        return populate_token_dictionary(response.json(), token_dictionary=token_dictionary)
    else:
        print(f"Request failed with status code {response.status_code}")
        print("Response content:", response.text)
        raise ValueError("Unable to refresh access token!")

def refresh_token_if_needed(token_dictionary:dict):
    if token_dictionary['access_token_expiration'] - timedelta(hours=1) < datetime.now():
        return refresh_token(token_dictionary=token_dictionary)
    else:
        return token_dictionary

def get_system_details(token_dictionary: dict):
    token_dictionary = refresh_token_if_needed(token_dictionary)
    url = "https://api.enphaseenergy.com/api/v4/systems"

    headers = {
        'Authorization': f'Bearer {token_dictionary['access_token']}',
        'key': api_key
    }

    # Make the POST request with basic authorization
    response = requests.get(url, headers=headers)
    time.sleep(10) #Avoid API rate limit errors

    # Check the response status code and content
    if response.status_code == 200:
        return token_dictionary, response.json()
    elif response.status_code == 429: #too many requests
        print(f"Request failed with status code {response.status_code} due to too many requests.")
        print("Response content:", response.text)
        time.sleep(30)
    else:
        print(f"Request failed with status code {response.status_code}")
        print("Response content:", response.text)
    raise ValueError("Unable to get system details!")

def get_system_summary(system_id: int, token_dictionary: dict):
    token_dictionary = refresh_token_if_needed(token_dictionary)
    url = f"https://api.enphaseenergy.com/api/v4/systems/{system_id}/summary"

    headers = {
        'Authorization': f'Bearer {token_dictionary['access_token']}',
        'key': api_key
    }

    # Make the POST request with basic authorization
    response = requests.get(url, headers=headers)
    time.sleep(10) #Avoid API rate limit errors

    # Check the response status code and content
    if response.status_code == 200:
        return token_dictionary, response.json()
    elif response.status_code == 429: #too many requests
        print(f"Request failed with status code {response.status_code} due to too many requests.")
        print("Response content:", response.text)
        time.sleep(30)
    else:
        print(f"Request failed with status code {response.status_code}")
        print("Response content:", response.text)
    raise ValueError("Unable to get system summary!")

def get_all_system_summaries(token_dictionary: dict):
    token_dictionary = refresh_token_if_needed(token_dictionary)
    #Call the APIs to get system summaries

    # Loop through the systems, populating a list of dictionaries
    token_dictionary, system_details = get_system_details(token_dictionary=token_dictionary)
    
    # Add system details
    system_dictionary_list = []
    if system_details is not None:
        for sys in system_details['systems']:
            token_dictionary, cur_system_summary = get_system_summary(sys['system_id'], token_dictionary=token_dictionary)
            cur_system_summary['name'] = sys['name']
            cur_system_summary['address'] = sys['address']
            system_dictionary_list.append(cur_system_summary)

    return token_dictionary, system_dictionary_list

def get_production_telemetry(token_dictionary: dict, system_id:int, granularity='day', start_at=None, start_date=None):
    token_dictionary = refresh_token_if_needed(token_dictionary)
    base_url = f"https://api.enphaseenergy.com/api/v4/systems/{system_id}/telemetry/production_meter"
    
    params = {
        }
    if start_at is not None:
        params['start_at'] = start_at
    if start_date is not None:
        params['start_date'] = start_date
    
    if len(params) == 0:
        url = base_url
    else:
        url = f"{base_url}?{urlencode(params)}"

    headers = {
        'Authorization': f'Bearer {token_dictionary['access_token']}',
        'key': api_key
    }

    # Make the POST request with basic authorization
    response = requests.get(url, headers=headers)
    time.sleep(10) #Avoid API rate limit errors

    # Check the response status code and content
    if response.status_code == 200:
        return token_dictionary, response.json()
    elif response.status_code == 429: #too many requests
        print(f"Request failed with status code {response.status_code} due to too many requests.")
        print("Response content:", response.text)
        time.sleep(30)
    else:
        print(f"Request failed with status code {response.status_code}")
        print("Response content:", response.text)
    raise ValueError("Unable to get production data!")
    
def get_consumption_telemetry(token_dictionary: dict, system_id:int, granularity='day', start_at=None, start_date=None):
    token_dictionary = refresh_token_if_needed(token_dictionary)
    base_url = f"https://api.enphaseenergy.com/api/v4/systems/{system_id}/telemetry/consumption_meter"
    
    params = {
        }
    if start_at is not None:
        params['start_at'] = start_at
    if start_date is not None:
        params['start_date'] = start_date
    
    if len(params) == 0:
        url = base_url
    else:
        url = f"{base_url}?{urlencode(params)}"

    headers = {
        'Authorization': f'Bearer {token_dictionary['access_token']}',
        'key': api_key
    }

    # Make the POST request with basic authorization
    response = requests.get(url, headers=headers)
    time.sleep(10) #Avoid API rate limit errors

    # Check the response status code and content
    if response.status_code == 200:
        return token_dictionary, response.json()
    elif response.status_code == 429: #too many requests
        print(f"Request failed with status code {response.status_code} due to too many requests.")
        print("Response content:", response.text)
        time.sleep(30)
    else:
        print(f"Request failed with status code {response.status_code}")
        print("Response content:", response.text)
    raise ValueError("Unable to get consumption data!")

def get_battery_telemetry(token_dictionary: dict, system_id:int, granularity='day', start_at=None, start_date=None):
    token_dictionary = refresh_token_if_needed(token_dictionary)
    base_url = f"https://api.enphaseenergy.com/api/v4/systems/{system_id}/telemetry/battery"
    
    params = {
        }
    if start_at is not None:
        params['start_at'] = start_at
    if start_date is not None:
        params['start_date'] = start_date
    
    if len(params) == 0:
        url = base_url
    else:
        url = f"{base_url}?{urlencode(params)}"

    headers = {
        'Authorization': f'Bearer {token_dictionary['access_token']}',
        'key': api_key
    }

    # Make the POST request with basic authorization
    response = requests.get(url, headers=headers)
    time.sleep(10) #Avoid API rate limit errors

    # Check the response status code and content
    if response.status_code == 200:
        return token_dictionary, response.json()
    elif response.status_code == 429: #too many requests
        print(f"Request failed with status code {response.status_code} due to too many requests.")
        print("Response content:", response.text)
        time.sleep(30)
    else:
        print(f"Request failed with status code {response.status_code}")
        print("Response content:", response.text)
    raise ValueError("Unable to get battery data!")
    
def get_energy_export_telemetry(token_dictionary: dict, system_id:int, granularity='day', start_at=None, start_date=None):
    token_dictionary = refresh_token_if_needed(token_dictionary)
    base_url = f"https://api.enphaseenergy.com/api/v4/systems/{system_id}/energy_export_telemetry"
    
    params = {
        }
    if start_at is not None:
        params['start_at'] = start_at
    if start_date is not None:
        params['start_date'] = start_date
    
    if len(params) == 0:
        url = base_url
    else:
        url = f"{base_url}?{urlencode(params)}"

    headers = {
        'Authorization': f'Bearer {token_dictionary['access_token']}',
        'key': api_key
    }

    # Make the POST request with basic authorization
    response = requests.get(url, headers=headers)
    time.sleep(10) #Avoid API rate limit errors

    # Check the response status code and content
    if response.status_code == 200:
        return token_dictionary, response.json()
    elif response.status_code == 429: #too many requests
        print(f"Request failed with status code {response.status_code} due to too many requests.")
        print("Response content:", response.text)
        time.sleep(30)
    else:
        print(f"Request failed with status code {response.status_code}")
        print("Response content:", response.text)
    raise ValueError("Unable to get energy export data!")

def get_energy_import_telemetry(token_dictionary: dict, system_id:int, granularity='day', start_at=None, start_date=None):
    token_dictionary = refresh_token_if_needed(token_dictionary)
    base_url = f"https://api.enphaseenergy.com/api/v4/systems/{system_id}/energy_import_telemetry"
    
    params = {
        }
    if start_at is not None:
        params['start_at'] = start_at
    if start_date is not None:
        params['start_date'] = start_date
    
    if len(params) == 0:
        url = base_url
    else:
        url = f"{base_url}?{urlencode(params)}"

    headers = {
        'Authorization': f'Bearer {token_dictionary['access_token']}',
        'key': api_key
    }

    # Make the POST request with basic authorization
    response = requests.get(url, headers=headers)
    time.sleep(10) #Avoid API rate limit errors

    # Check the response status code and content
    if response.status_code == 200:
        return token_dictionary, response.json()
    elif response.status_code == 429: #too many requests
        print(f"Request failed with status code {response.status_code} due to too many requests.")
        print("Response content:", response.text)
        time.sleep(30)
    else:
        print(f"Request failed with status code {response.status_code}")
        print("Response content:", response.text)
    raise ValueError("Unable to get energy import data!")

