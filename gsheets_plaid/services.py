import json
import os

import googleapiclient.discovery
import plaid
from google.oauth2.credentials import Credentials
from plaid.api import plaid_api

GOOGLE_SCOPES = [
    'https://www.googleapis.com/auth/drive.file',
    'openid',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/userinfo.email',
]


def generate_plaid_client(
        plaid_env: str,
        plaid_client_id: str,
        plaid_secret: str) -> plaid_api.PlaidApi:
    if plaid_env == 'sandbox':
        host = plaid.Environment.Sandbox
    elif plaid_env == 'development':
        host = plaid.Environment.Development
    elif plaid_env == 'production':
        host = plaid.Environment.Production
    else:
        host = plaid.Environment.Sandbox

    plaid_config = plaid.Configuration(
        host=host,
        api_key={
            'clientId': plaid_client_id,
            'secret': plaid_secret,
            'plaidVersion': '2020-09-14',
        }
    )

    api_client = plaid.ApiClient(plaid_config)
    plaid_client = plaid_api.PlaidApi(api_client)
    return plaid_client


def generate_gsheets_service(credentials: Credentials | dict | str) -> googleapiclient.discovery.Resource:
    if isinstance(credentials, dict):
        credentials = Credentials.from_authorized_user_info(credentials, GOOGLE_SCOPES)
    elif isinstance(credentials, str) and os.path.isfile(credentials):
        credentials = Credentials.from_authorized_user_file(credentials, GOOGLE_SCOPES)
    elif isinstance(credentials, str):
        try:
            credentials = Credentials.from_authorized_user_info(json.loads(credentials), GOOGLE_SCOPES)
        except json.JSONDecodeError:
            raise ValueError('Credentials file is not valid JSON.')
    elif not isinstance(credentials, Credentials):
        msg = "'credentials' must be a Credentials object, a dict, a JSON string, or a string filepath."
        raise TypeError(msg)
    service = googleapiclient.discovery.build('sheets', 'v4', credentials=credentials)
    return service
