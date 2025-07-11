import webbrowser
from urllib.parse import urlencode
import os
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta
import time
from tzlocal import get_localzone
import pytz

#Requires a developer account and a registered developer app.
#
# Looks for the following environment variables:
#   ENPHASE_API_KEY
#   ENPHASE_CLIENT_ID
#   ENPHASE_CLIENT_SECRET

api_key = os.getenv('ENPHASE_API_KEY')
client_id = os.getenv('ENPHASE_CLIENT_ID')
client_secret = os.getenv('ENPHASE_CLIENT_SECRET')

MAX_API_CALLS_PER_MINUTE = 10 #Free API limit

class APICallFrequencyMonitor():
    def __init__(self):
        self.max_calls_per_minute = MAX_API_CALLS_PER_MINUTE
        self.api_call_history = [] # List to store timestamps of API calls

    def record_api_call(self):
        current_time = datetime.now()
        # Remove calls older than 1 minute
        self.api_call_history = [t for t in self.api_call_history if t > current_time - timedelta(minutes=1)]
        self.api_call_history.append(current_time)

    def can_make_api_call(self) -> bool:
        # Using over 80% of the API call limit triggers emails
        return len(self.api_call_history) < (self.max_calls_per_minute * 0.8)
    
    def wait_for_next_api_call_and_record(self):
        if not self.can_make_api_call():
            # Calculate how long to wait until we can make the next API call
            oldest_call_time = self.api_call_history[0]
            wait_time = (oldest_call_time + timedelta(minutes=1)) - datetime.now()
            if wait_time.total_seconds() > 0:
                print(f"Waiting for {wait_time.total_seconds()} seconds until next API call.")
                time.sleep(wait_time.total_seconds())
        self.record_api_call()

api_monitor = APICallFrequencyMonitor()

# Ensure that the environment variables are set
if not api_key or not client_id or not client_secret:
    raise ValueError("Not all ENPHASE API environment variables are set")

# Get the local timezone automatically
local_tz = get_localzone()

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
    api_monitor.wait_for_next_api_call_and_record()
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
    api_monitor.wait_for_next_api_call_and_record()
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
    api_monitor.wait_for_next_api_call_and_record() # Avoid API rate limit errors
    response = requests.get(url, headers=headers)

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
    api_monitor.wait_for_next_api_call_and_record() # Avoid API rate limit errors
    response = requests.get(url, headers=headers)

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

def get_production_telemetry(token_dictionary: dict, system_id:int, granularity='week', start_at=None, start_date=None):
    token_dictionary = refresh_token_if_needed(token_dictionary)
    base_url = f"https://api.enphaseenergy.com/api/v4/systems/{system_id}/telemetry/production_meter"
    
    params = {
        'granularity': granularity
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
    api_monitor.wait_for_next_api_call_and_record() # Avoid API rate limit errors
    response = requests.get(url, headers=headers)

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
    
def get_consumption_telemetry(token_dictionary: dict, system_id:int, granularity='week', start_at=None, start_date=None):
    token_dictionary = refresh_token_if_needed(token_dictionary)
    base_url = f"https://api.enphaseenergy.com/api/v4/systems/{system_id}/telemetry/consumption_meter"
    
    params = {
        'granularity': granularity
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
    api_monitor.wait_for_next_api_call_and_record() # Avoid API rate limit errors
    response = requests.get(url, headers=headers)

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

def get_battery_telemetry(token_dictionary: dict, system_id:int, granularity='week', start_at=None, start_date=None):
    token_dictionary = refresh_token_if_needed(token_dictionary)
    base_url = f"https://api.enphaseenergy.com/api/v4/systems/{system_id}/telemetry/battery"
    
    params = {
        'granularity': granularity
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
    api_monitor.wait_for_next_api_call_and_record() # Avoid API rate limit errors
    response = requests.get(url, headers=headers)

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
    
def get_energy_export_telemetry(token_dictionary: dict, system_id:int, granularity='week', start_at=None, start_date=None):
    token_dictionary = refresh_token_if_needed(token_dictionary)
    base_url = f"https://api.enphaseenergy.com/api/v4/systems/{system_id}/energy_export_telemetry"
    
    params = {
        'granularity': granularity
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
    api_monitor.wait_for_next_api_call_and_record() # Avoid API rate limit errors
    response = requests.get(url, headers=headers)

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

def get_energy_import_telemetry(token_dictionary: dict, system_id:int, granularity='week', start_at=None, start_date=None):
    token_dictionary = refresh_token_if_needed(token_dictionary)
    base_url = f"https://api.enphaseenergy.com/api/v4/systems/{system_id}/energy_import_telemetry"
    
    params = {
        'granularity': granularity
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
    api_monitor.wait_for_next_api_call_and_record() # Avoid API rate limit errors
    response = requests.get(url, headers=headers)

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

def enphase_epoch_to_datetime_noDST(enphase_ts:int):
    """
    Convert the enphase time (epoch format) to a datetime,
    shifting it to the proper GMT non-DST.
    """
    dt = datetime.fromtimestamp(enphase_ts)
    
    #There seems to be a bug with the Enphase API
    #where the epoch jumps an hour when entering DST
    #Try to fix so we're always treating without DST

    # Attach tzinfo (naively) and adjust for DST
    dt_with_tz = dt.replace(tzinfo=local_tz)
    dt_withdst = dt_with_tz.astimezone(local_tz)

    # Check if DST is active
    if bool(dt_with_tz.dst()):
        #localized dt has been pushed ahead an hour for daylight savings time
        dt = dt - dt_with_tz.dst()

    return dt
