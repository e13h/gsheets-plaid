import json
import os
from importlib.resources import files

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from gsheets_plaid.initialization import CONFIG

SCOPES = ['https://www.googleapis.com/auth/drive.file']
TOKEN_PKG = 'gsheets_plaid.resources.db.tokens'


def load_creds(scopes: list[str]) -> Credentials:
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
                creds = generate_new_creds()
        else:
            creds = generate_new_creds()
        # Save the credentials for the next run
        with open(token_resource, 'w') as token:
            token.write(creds.to_json())
    return creds


def generate_new_creds() -> Credentials:
    creds_filename = CONFIG.get('GOOGLE_CREDENTIAL_FILENAME')
    creds_resource = files(TOKEN_PKG).joinpath(creds_filename)
    assert creds_resource.is_file()
    flow = InstalledAppFlow.from_client_secrets_file(creds_resource, SCOPES)
    creds = flow.run_local_server(port=0)
    return creds


creds = load_creds(SCOPES)
gsheets_service = build('sheets', 'v4', credentials=creds)


def get_spreadsheet_id(verbose: str = False) -> str:
    """Get the spreadsheet ID, or create a new one
    """
    spreadsheet_id = None
    token_pkg = 'gsheets_plaid.resources.db.tokens'
    config_filename = CONFIG.get('GOOGLE_SHEETS_CONFIG_FILENAME')
    config_resource = files(token_pkg).joinpath(config_filename)
    if config_resource.is_file():
        if verbose:
            print('Found an existing spreadsheet...')
        with open(config_resource) as config_file:
            config = json.load(config_file)
        spreadsheet_id = config.get("spreadsheetId")
    else:
        if verbose:
            print('Creating a new spreadsheet...')
        spreadsheet = {'properties': {'title': 'Finance Tracker'}}
        result = gsheets_service.spreadsheets().create(body=spreadsheet).execute()
        spreadsheet_id = result.get("spreadsheetId")
        with open(config_resource, 'w') as config_file:
            json.dump({"spreadsheetId": spreadsheet_id}, config_file)
    return spreadsheet_id


def main():
    """Print the spreadsheet ID.
    """
    spreadsheet_id = get_spreadsheet_id()
    print(spreadsheet_id)


if __name__ == '__main__':
    main()
