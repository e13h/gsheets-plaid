import functions_framework
import flask
from gsheets_plaid.services import generate_gsheets_service, generate_plaid_client
from gsheets_plaid.sync import sync_transactions


@functions_framework.http
def sync_http(request: flask.Request):
    content_type = request.headers['content-type']
    if content_type != 'application/json':
        raise ValueError(f'Expected content-type to be application/json, not {content_type}')
    request_json = request.get_json(silent=True)
    if not request_json:
        raise ValueError('Expected request body to be JSON!')
    google_credentials = request_json['google_credentials']
    plaid_env = request_json['plaid_env']
    plaid_client_id = request_json['plaid_client_id']
    plaid_secret = request_json['plaid_secret']
    access_tokens = request_json['access_tokens']
    spreadsheet_id = request_json['spreadsheet_id']
    gsheets_service = generate_gsheets_service(google_credentials)
    plaid_client = generate_plaid_client(plaid_env, plaid_client_id, plaid_secret)
    sync_transactions(gsheets_service, plaid_client, access_tokens, spreadsheet_id)
    return 'Success'
