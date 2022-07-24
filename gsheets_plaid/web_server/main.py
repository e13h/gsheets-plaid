import io
import json
import os
from datetime import datetime, timedelta

import google_auth_oauthlib.flow
import googleapiclient.errors
from dotenv import load_dotenv
from flask import Flask, make_response, redirect, render_template, request, session, url_for
from google.auth.exceptions import RefreshError
from google.auth.transport import requests
from google.auth.transport.requests import Request as GoogleRequest
from google.cloud import firestore, secretmanager
from google.oauth2 import id_token
from google.oauth2.credentials import Credentials
from gsheets_plaid.create_sheet import create_new_spreadsheet
from gsheets_plaid.services import GOOGLE_SCOPES, generate_gsheets_service, generate_plaid_client
from gsheets_plaid.sync import get_spreadsheet_url, sync_transactions
from gsheets_plaid.web_server.session_manager import FirestoreSessionManager, FlaskSessionManager
from plaid.api import plaid_api
from plaid.exceptions import ApiException as PlaidApiException
from plaid.model.country_code import CountryCode
from plaid.model.institutions_get_by_id_request import InstitutionsGetByIdRequest
from plaid.model.institutions_get_request import InstitutionsGetRequest
from plaid.model.item_get_request import ItemGetRequest
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products

TIMESTAMP_FORMAT = '%Y-%m-%dT%H:%M:%S'

app = Flask(__name__)
plaid_client = None
if os.environ.get('GOOGLE_CLOUD_PROJECT'):
    session_manager = FirestoreSessionManager(firestore.Client())
    print('Using Firestore session manager')
else:
    session_manager = FlaskSessionManager(session)
    print('Using Flask session manager')

@app.before_first_request
def initialize_app():
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.isfile(env_file):
        load_dotenv()
    elif os.environ.get('GOOGLE_CLOUD_PROJECT'):
        project_id = os.environ.get('GOOGLE_CLOUD_PROJECT')
        secrets_client = secretmanager.SecretManagerServiceClient()
        name = f'projects/{project_id}/secrets/app_engine_python_env/versions/latest'
        payload = secrets_client.access_secret_version(name=name).payload.data.decode('UTF-8')
        load_dotenv(stream=io.StringIO(payload))
    else:
        raise Exception("No local .env or GOOGLE_CLOUD_PROJECT detected. No secrets found.")

@app.route('/login')
def login():
    return render_template('login.html', client_id=os.environ.get('GOOGLE_CLOUD_CLIENT_ID'))

@app.route('/')
@app.route('/index')
def index():
    if not session_manager.user_id:
        user_id = request.cookies.get('user_id')
        if not user_id:
            return redirect(url_for('login'))
        session_manager.register_user_id(user_id)
    try:
        session_data = session_manager.get_session()
    except Exception:
        return redirect(url_for('login'))
    return render_template('checklist.html', **status_check(session_data), username=session_data.get('greeting_name'))

@app.route('/sign-in-with-google-callback')
def sign_in_with_google_callback():
    token = request.args.get('jwt')
    if not token:
        raise KeyError('No token found!')
    try:
        id_info = id_token.verify_oauth2_token(token, requests.Request(), os.environ.get('GOOGLE_CLOUD_CLIENT_ID'))
        session_manager.register_user_id(id_info['sub'])
        session_data = session_manager.get_session()
        session_data['user_id'] = id_info['sub']
        session_data['greeting_name'] = id_info['given_name']
        session_manager.set_session(session_data)
    except ValueError:
        raise ValueError('Invalid token!')
    resp = redirect(url_for('index'))
    resp.set_cookie('user_id', id_info['sub'], httponly=True)
    return resp

@app.route('/sign-out')
def sign_out():
    session_manager.clear_session()
    resp = redirect(url_for('index'))
    resp.delete_cookie('user_id', httponly=True)
    return resp

@app.route('/edit-plaid-credentials', methods=['GET', 'POST'])
def edit_plaid_credentials():
    session_data = session_manager.get_session()
    if request.method == 'GET':
        plaid_client_id = session_data.get('plaid_client_id', '')
        plaid_secret_sandbox = session_data.get('plaid_secret_sandbox', '')
        plaid_secret_development = session_data.get('plaid_secret_development', '')
        plaid_secret_production = session_data.get('plaid_secret_production', '')
        return render_template('plaid_credentials_form.html',
            plaid_env=session_data.get('plaid_env'),
            plaid_client_id=plaid_client_id,
            plaid_secret_sandbox=plaid_secret_sandbox,
            plaid_secret_development=plaid_secret_development,
            plaid_secret_production=plaid_secret_production,
            plaid_sandbox_creds_valid=validate_plaid_credentials('sandbox', plaid_client_id, plaid_secret_sandbox),
            plaid_development_creds_valid=validate_plaid_credentials('development', plaid_client_id, plaid_secret_development),
            plaid_production_creds_valid=validate_plaid_credentials('production', plaid_client_id, plaid_secret_production))
    elif request.method == 'POST':
        session_data['plaid_env'] = request.form['plaid_env']
        session_data['plaid_client_id'] = request.form['plaid_client_id']
        session_data['plaid_secret_sandbox'] = request.form['plaid_secret_sandbox']
        session_data['plaid_secret_development'] = request.form['plaid_secret_development']
        session_data['plaid_secret_production'] = request.form['plaid_secret_production']
        session_manager.set_session(session_data)
        global plaid_client
        plaid_client = None
        return redirect(url_for('edit_plaid_credentials'))
    else:
        raise ValueError('Invalid request method')

@app.template_filter('unquote')
def unquote(url):
    import urllib.parse
    safe = app.jinja_env.filters['safe']
    return safe(urllib.parse.unquote(url))

@app.route('/authorize-google-credentials')
def authorize_google_credentials():
    # Create flow instance to manage the OAuth 2.0 Authorization Grant Flow steps.
    client_config = json.loads(os.environ.get('GOOGLE_CLOUD_CLIENT_CONFIG', {}))
    flow = google_auth_oauthlib.flow.Flow.from_client_config(client_config, GOOGLE_SCOPES)

    # The URI created here must exactly match one of the authorized redirect URIs
    # for the OAuth 2.0 client, which you configured in the API Console. If this
    # value doesn't match an authorized URI, you will get a 'redirect_uri_mismatch'
    # error.
    flow.redirect_uri = url_for('google_oauth_callback', _external=True)

    authorization_url, state = flow.authorization_url(
        # Enable offline access so that you can refresh an access token without
        # re-prompting the user for permission. Recommended for web server apps.
        access_type='offline',
        # Enable incremental authorization. Recommended as a best practice.
        include_granted_scopes='true')

    # Store the state so the callback can verify the auth server response.
    resp = redirect(authorization_url)
    resp.set_cookie('google_oauth_state', state, httponly=True)
    return resp

@app.route('/google-oauth-callback')
def google_oauth_callback():
    # Specify the state when creating the flow in the callback so that it can
    # verified in the authorization server response.
    state = request.cookies.get('google_oauth_state')
    client_config = json.loads(os.environ.get('GOOGLE_CLOUD_CLIENT_CONFIG', {}))
    flow = google_auth_oauthlib.flow.Flow.from_client_config(client_config, GOOGLE_SCOPES, state=state)
    flow.redirect_uri = url_for('google_oauth_callback', _external=True)

    # Use the authorization server's response to fetch the OAuth 2.0 tokens.
    flow.fetch_token(authorization_response=request.url)

    # Store credentials in the session.
    # ACTION ITEM: In a production app, you likely want to save these
    #              credentials in a persistent database instead.
    session_manager['google_credentials'] = json.loads(flow.credentials.to_json())

    resp = redirect(url_for('index'))
    resp.delete_cookie('google_oauth_state', httponly=True)
    return resp

@app.route('/manage-spreadsheets', methods=['GET', 'POST'])
def manage_spreadsheets():
    session_data = session_manager.get_session()
    try:
        google_credentials = session_data['google_credentials']
        gsheets_service = build_gsheets_service(google_credentials)
    except (ValueError, KeyError):
        return redirect(url_for('authorize_google_credentials'))
    if request.method == 'GET':
        return render_template('google_spreadsheet_form.html',
            plaid_env=session_data.get('plaid_env'),
            sandbox_spreadsheet_name=lookup_spreadsheet_name_for_env('sandbox', gsheets_service, session_data),
            development_spreadsheet_name=lookup_spreadsheet_name_for_env('development', gsheets_service, session_data),
            production_spreadsheet_name=lookup_spreadsheet_name_for_env('production', gsheets_service, session_data),
            )
    elif request.method == 'POST':
        for plaid_env in ('sandbox', 'development', 'production'):
            title = request.form.get(f'{plaid_env}_spreadsheet_name')
            if title:
                spreadsheet_id = create_new_spreadsheet(gsheets_service, title)
                session_data[f'{plaid_env}_spreadsheet_id'] = spreadsheet_id
                session_data[f'{plaid_env}_spreadsheet_url'] = get_spreadsheet_url(gsheets_service, spreadsheet_id)
        session_manager.set_session(session_data)
        return redirect(url_for('manage_spreadsheets'))
    else:
        raise ValueError('Invalid request method')

@app.route('/manage-plaid-items')
def manage_plaid_items():
    session_data = session_manager.get_session()
    link_token = request_link_token(session_data)
    if not link_token:
        return f"""
        An error occurred when authenticating with Plaid. Make sure that you whitelist the
        following redirect URI in the
        <a href="https://dashboard.plaid.com/team/api" target="_blank">Plaid Dashboard</a>.<br>
        <samp>{url_for('plaid_oauth_callback', _external=True)}</samp>
        <br><br>
        <a href={url_for('index')}>Back to home</a>
        """
    access_tokens = get_plaid_items(session_data).values()
    item_info = get_plaid_item_info(access_tokens, session_data)
    resp = make_response(render_template('plaid_items_form.html', plaid_link_token=link_token,
        plaid_oauth_redirect=False, plaid_items=item_info))
    resp.set_cookie('plaid_link_token', link_token, httponly=True)
    return resp

@app.route('/plaid-oauth-callback')
def plaid_oauth_callback():
    link_token = request.cookies.get('plaid_link_token')
    if not link_token:
        return redirect(url_for('manage_plaid_items'))
    resp = make_response(render_template('plaid_items_form.html', plaid_link_token=link_token,
        plaid_oauth_redirect=True))
    resp.delete_cookie('plaid_link_token', httponly=True)
    return resp

@app.route('/plaid-link-success')
def plaid_link_success():
    public_token = request.args.get('public_token')
    session_data = session_manager.get_session()
    item_id, access_token = item_public_token_exchange(public_token, session_data)
    if 'plaid_items' not in session_data:
        session_data['plaid_items'] = {}
    session_data['plaid_items'][item_id] = access_token
    session_manager.set_session(session_data)
    return redirect(url_for('manage_plaid_items'))

@app.route('/sync')
def sync():
    session_data = session_manager.get_session()
    if not user_allowed_sync(session_data):
        return f'''
        <h1>Error</h1>
        <p>You are not allowed to sync more than once every 12 hours.<p><br>
        <a href={url_for('index')}>Back to home</a>
        '''
    num_days = request.args.get('days', default=30, type=int)
    try:
        google_credentials = session_data['google_credentials']
        gsheets_service = build_gsheets_service(google_credentials)
    except (ValueError, KeyError):
        return redirect(url_for('authorize_google_credentials'))
    plaid_client = build_plaid_client(session_data)
    plaid_access_tokens = get_plaid_items(session_data).values()
    plaid_env = session_data.get('plaid_env', 'sandbox')
    spreadsheet_id = session_data.get(f'{plaid_env}_spreadsheet_id')
    sync_transactions(gsheets_service, plaid_client, plaid_access_tokens, spreadsheet_id, num_days)
    session_manager['last_sync'] = datetime.now().strftime(TIMESTAMP_FORMAT)
    return redirect(url_for('index'))

def status_check(session_data: dict) -> dict:
    plaid_env = session_data.get('plaid_env', 'sandbox')
    plaid_items = get_plaid_items(session_data)
    return {
        'google_creds_status': 'google_credentials' in session_data,
        'spreadsheet_exists': f'{plaid_env}_spreadsheet_id' in session_data and f'{plaid_env}_spreadsheet_url' in session_data,
        'plaid_creds_status': validate_plaid_credentials(plaid_env, session_data.get('plaid_client_id'), session_data.get(f'plaid_secret_{plaid_env}')),
        'plaid_access_tokens_status': validate_plaid_access_tokens(plaid_items, session_data),
        'spreadsheet_url': session_data.get(f'{plaid_env}_spreadsheet_url'),
    }


def user_allowed_sync(session_data: dict) -> bool:
    last_sync = session_data.get('last_sync')
    if not last_sync:
        return True
    last_sync = datetime.strptime(last_sync, TIMESTAMP_FORMAT)
    interval = timedelta(hours=12)
    if last_sync + interval < datetime.now():
        return True
    return False

def validate_plaid_credentials(plaid_env: str, client_id: str, secret: str) -> bool:
    if not all([plaid_env, client_id, secret]):
        return False
    try:
        plaid_client = generate_plaid_client(plaid_env, client_id, secret)
        plaid_request = InstitutionsGetRequest(country_codes=[CountryCode('US')], count=1, offset=0)
        plaid_client.institutions_get(plaid_request)
    except PlaidApiException:
        return False
    return True

def validate_plaid_access_tokens(plaid_items: dict, session_data: dict) -> bool:
    if len(plaid_items) == 0:
        return None
    plaid_client = build_plaid_client(session_data)
    for access_token in plaid_items.values():
        try:
            plaid_client.item_get(ItemGetRequest(access_token))
        except PlaidApiException:
            return False
    return True

def get_plaid_items(session_data: dict) -> dict:
    plaid_env = session_data.get('plaid_env', 'sandbox')
    plaid_items = session_data.get('plaid_items', {})
    return {k: v for k, v in plaid_items.items() if v.lower().startswith(f'access-{plaid_env}')}

def lookup_spreadsheet_name_for_env(
        plaid_env: str,
        gsheets_service: googleapiclient.discovery.Resource,
        session_data: dict) -> str:
    if plaid_env not in ('sandbox', 'development', 'production'):
        raise ValueError(plaid_env)
    spreadsheet_id = session_data.get(f'{plaid_env}_spreadsheet_id')
    if not spreadsheet_id:
        return ''
    try:
        result = gsheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        return result['properties']['title']
    except googleapiclient.errors.HttpError:
        del session_manager[f'{plaid_env}_spreadsheet_id']
        return ''

def build_gsheets_service(google_credentials: dict) -> googleapiclient.discovery.Resource:
    credentials = Credentials.from_authorized_user_info(google_credentials, GOOGLE_SCOPES)
    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(GoogleRequest())
            session_manager['google_credentials'] = json.loads(credentials.to_json())
        except RefreshError:  # Refresh token expired
            pass
    if not credentials.valid:
        del session_manager['google_credentials']
        raise ValueError('Invalid Google credentials')
    gsheets_service = generate_gsheets_service(credentials)
    return gsheets_service

def request_link_token(session_data: dict) -> str:
    plaid_client = build_plaid_client(session_data)
    request = LinkTokenCreateRequest(
        products=[Products('transactions')],
        client_name="GSheets-Plaid",
        country_codes=[CountryCode('US')],
        redirect_uri=url_for('plaid_oauth_callback', _external=True),
        language='en',
        link_customization_name='default',
        user=LinkTokenCreateRequestUser(
            client_user_id=session_data['user_id']
        ))
    try:
        response = plaid_client.link_token_create(request)
        link_token = response['link_token']
    except PlaidApiException as e:
        print(e)
        link_token = None
    return link_token

def request_link_update_token(
        plaid_client: plaid_api.PlaidApi,
        access_token: str,
        session_data: dict) -> str:
    request = LinkTokenCreateRequest(
        client_name="GSheets-Plaid",
        country_codes=[CountryCode('US')],
        redirect_uri=url_for('plaid_oauth_callback', _external=True),
        language='en',
        link_customization_name='default',
        user=LinkTokenCreateRequestUser(
            client_user_id=session_data['user_id']
        ),
        access_token=access_token)
    try:
        response = plaid_client.link_token_create(request)
        link_token = response['link_token']
    except PlaidApiException as e:
        print(e)
        link_token = None
    return link_token

def build_plaid_client(session_data: dict) -> plaid_api.PlaidApi:
    global plaid_client
    if plaid_client is not None:
        return plaid_client
    plaid_env = session_data.get('plaid_env', 'sandbox')
    if plaid_env not in ('sandbox', 'development', 'production'):
        raise ValueError(plaid_env)
    plaid_client_id = session_data.get('plaid_client_id')
    plaid_secret = session_data.get(f'plaid_secret_{plaid_env}')
    if not validate_plaid_credentials(plaid_env, plaid_client_id, plaid_secret):
        raise ValueError('Invalid Plaid credentials')
    plaid_client = generate_plaid_client(plaid_env, plaid_client_id, plaid_secret)
    return plaid_client

def item_public_token_exchange(public_token: str, session_data: dict) -> tuple[str, str]:
    plaid_client = build_plaid_client(session_data)
    request = ItemPublicTokenExchangeRequest(public_token=public_token)
    response = plaid_client.item_public_token_exchange(request)
    access_token = response['access_token']
    item_id = response['item_id']
    return item_id, access_token

def get_plaid_item_info(access_tokens: list, session_data: dict) -> tuple:
    results = []
    plaid_client = build_plaid_client(session_data)
    for token in access_tokens:
        try:
            response = plaid_client.item_get(ItemGetRequest(token))
            ins_id = response['item']['institution_id']
            ins_request = InstitutionsGetByIdRequest(ins_id, [CountryCode('US')])
            response = plaid_client.institutions_get_by_id(ins_request)
            link_update_token = request_link_update_token(plaid_client, token, session_data)
            results.append((response['institution']['name'], True, link_update_token))
        except PlaidApiException as e:
            raise e
    return results

@app.route('/revoke-google-credentials')
def revoke():
    session_data = session_manager.get_session_data()
    raw_credentials = session_data.get('google_credentials')
    if not raw_credentials:
        return ('You need to <a href="/authorize-google-credentials">authorize</a> before ' +
                'testing the code to revoke credentials.')
    credentials = Credentials.from_authorized_user_info(raw_credentials, GOOGLE_SCOPES)

    revoke = requests.post('https://oauth2.googleapis.com/revoke',
        params={'token': credentials.token},
        headers = {'content-type': 'application/x-www-form-urlencoded'})

    status_code = getattr(revoke, 'status_code')
    if status_code == 200:
        return 'Credentials successfully revoked.'
    else:
        return 'An error occurred.'

def run_web_server(host: str = 'localhost', port: int = 8080, debug: bool = False, **kwargs):
    app.run(host=host, port=port, debug=debug, load_dotenv=False, **kwargs)

if __name__ == '__main__':
    run_web_server()
