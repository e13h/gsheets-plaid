import json
import os
from importlib.resources import files

import googleapiclient.discovery
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from gsheets_plaid.create_sheet import create_new_spreadsheet
from gsheets_plaid.initialization import CONFIG

TOKEN_PKG = 'gsheets_plaid.resources.db.tokens'


def get_access_tokens() -> list[str]:
    """Load the access tokens from file.
    """
    token_filename = CONFIG.get('PLAID_TOKENS_OUTPUT_FILENAME')
    token_resource = files(TOKEN_PKG).joinpath(token_filename)
    with open(token_resource, 'r') as file:
        tokens = json.load(file)
    env_str = CONFIG.get('PLAID_ENV', 'sandbox').lower()
    tokens = [token['access_token'] for token in tokens if token['access_token'].startswith(f'access-{env_str}')]
    return tokens


def load_creds_from_file(scopes: list[str]) -> Credentials:
    """Load or create credentials for Google Sheets API.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    token_resource = files(TOKEN_PKG).joinpath(CONFIG.get('GOOGLE_TOKEN_FILENAME'))
    if token_resource.is_file():
        creds: Credentials = Credentials.from_authorized_user_file(token_resource, scopes)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                # Refresh token expired
                os.remove(token_resource)
                creds = generate_new_creds_from_secrets_file(scopes)
        else:
            creds = generate_new_creds_from_secrets_file(scopes)
        # Save the credentials for the next run
        with open(token_resource, 'w') as token:
            token.write(creds.to_json())
    return creds


def generate_new_creds_from_secrets_file(scopes: list[str]) -> Credentials:
    creds_filename = CONFIG.get('GOOGLE_CREDENTIAL_FILENAME')
    creds_resource = files(TOKEN_PKG).joinpath(creds_filename)
    assert creds_resource.is_file()
    flow = InstalledAppFlow.from_client_secrets_file(creds_resource, scopes)
    creds = flow.run_local_server(port=0)
    return creds


def get_spreadsheet_id_from_file(
        gsheets_service: googleapiclient.discovery.Resource,
        verbose: bool = False) -> str:
    """Get the spreadsheet ID, or create a new one
    """
    spreadsheet_id = None
    config_filename = CONFIG.get('GOOGLE_SHEETS_CONFIG_FILENAME')
    config_resource = files(TOKEN_PKG).joinpath(config_filename)
    if config_resource.is_file():
        if verbose:
            print('Found an existing spreadsheet...')
        with open(config_resource) as config_file:
            config = json.load(config_file)
        spreadsheet_id = config.get("spreadsheetId")
    else:
        if verbose:
            print('Creating a new spreadsheet...')
        spreadsheet_id = create_new_spreadsheet(gsheets_service)
        with open(config_resource, 'w') as config_file:
            json.dump({"spreadsheetId": spreadsheet_id}, config_file)
    return spreadsheet_id
