import json
import os
from datetime import datetime, timedelta

import google_auth_oauthlib.flow
import googleapiclient.errors
import requests
from flask import Flask, redirect, render_template, request, session, url_for
from google.auth.exceptions import RefreshError
from google.auth.transport import requests
from google.auth.transport.requests import Request as GoogleRequest
from google.cloud import firestore
from google.oauth2 import id_token
from google.oauth2.credentials import Credentials
from gsheets_plaid.create_sheet import create_new_spreadsheet
from gsheets_plaid.services import GOOGLE_SCOPES, generate_gsheets_service, generate_plaid_client
from gsheets_plaid.sync import get_spreadsheet_url, sync_transactions
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
db = None

@app.before_first_request
def initialize_app():
    global db
    db = firestore.Client(project=os.environ.get('GOOGLE_CLOUD_PROJECT_ID'))
    Flask.secret_key = os.environ.get('FLASK_SECRET_KEY')

@app.route('/login')
def login():
    return render_template('login.html', client_id=os.environ.get('GOOGLE_CLOUD_CLIENT_ID'))

@app.route('/')
@app.route('/index')
def index():
    user_info = session.get('user_info')
    if not user_info:
        return redirect(url_for('login'))
    return render_template('checklist.html',
        google_creds_status=validate_google_credentials(),
        spreadsheet_exists=validate_spreadsheet_exists(),
        plaid_creds_status=validate_user_set_plaid_credentials(),
        plaid_access_tokens_status=validate_plaid_access_tokens(),
        spreadsheet_url=fetch_spreadsheet_url())

@app.route('/sign-in-with-google-callback')
def sign_in_with_google_callback():
    token = request.args.get('jwt')
    if not token:
        raise KeyError('No token found!')
    try:
        id_info = id_token.verify_oauth2_token(token, requests.Request(), os.environ.get('GOOGLE_CLOUD_CLIENT_ID'))
        session['user_info'] = id_info
    except ValueError:
        # Invalid token
        pass
    return redirect(url_for('index'))

@app.route('/sign-out')
def sign_out():
    session.pop('user_info', None)
    return redirect(url_for('index'))

@app.route('/edit-plaid-credentials', methods=['GET', 'POST'])
def edit_plaid_credentials():
    if request.method == 'GET':
        user_settings = get_current_user()
        plaid_client_id = user_settings.get('plaid_client_id', '')
        plaid_secret_sandbox = user_settings.get('plaid_secret_sandbox', '')
        plaid_secret_development = user_settings.get('plaid_secret_development', '')
        plaid_secret_production = user_settings.get('plaid_secret_production', '')
        return render_template('plaid_credentials_form.html',
            plaid_env=user_settings.get('plaid_env'),
            plaid_client_id=plaid_client_id,
            plaid_secret_sandbox=plaid_secret_sandbox,
            plaid_secret_development=plaid_secret_development,
            plaid_secret_production=plaid_secret_production,
            plaid_sandbox_creds_valid=validate_plaid_credentials('sandbox', plaid_client_id, plaid_secret_sandbox),
            plaid_development_creds_valid=validate_plaid_credentials('development', plaid_client_id, plaid_secret_development),
            plaid_production_creds_valid=validate_plaid_credentials('production', plaid_client_id, plaid_secret_production))
    elif request.method == 'POST':
        get_current_user()
        session['user_settings']['plaid_env'] = request.form['plaid_env']
        session['user_settings']['plaid_client_id'] = request.form['plaid_client_id']
        session['user_settings']['plaid_secret_sandbox'] = request.form['plaid_secret_sandbox']
        session['user_settings']['plaid_secret_development'] = request.form['plaid_secret_development']
        session['user_settings']['plaid_secret_production'] = request.form['plaid_secret_production']
        session.modified = True
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
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        os.environ.get('GOOGLE_CLOUD_CLIENT_SECRETS_FILE'), scopes=GOOGLE_SCOPES)

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
    session['google_oauth_state'] = state

    return redirect(authorization_url)

@app.route('/google-oauth-callback')
def google_oauth_callback():
    # Specify the state when creating the flow in the callback so that it can
    # verified in the authorization server response.
    state = session['google_oauth_state']

    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        os.environ.get('GOOGLE_CLOUD_CLIENT_SECRETS_FILE'), scopes=GOOGLE_SCOPES, state=state)
    flow.redirect_uri = url_for('google_oauth_callback', _external=True)

    # Use the authorization server's response to fetch the OAuth 2.0 tokens.
    flow.fetch_token(authorization_response=request.url)

    # Store credentials in the session.
    # ACTION ITEM: In a production app, you likely want to save these
    #              credentials in a persistent database instead.
    session['user_settings']['google_credentials'] = json.loads(flow.credentials.to_json())
    session.modified = True

    return redirect(url_for('index'))

@app.route('/manage-spreadsheets', methods=['GET', 'POST'])
def manage_spreadsheets():
    user_settings = get_current_user()
    if request.method == 'GET':
        return render_template('google_spreadsheet_form.html',
            plaid_env=user_settings.get('plaid_env'),
            sandbox_spreadsheet_name=lookup_spreadsheet_name_for_env('sandbox'),
            development_spreadsheet_name=lookup_spreadsheet_name_for_env('development'),
            production_spreadsheet_name=lookup_spreadsheet_name_for_env('production'),
            )
    elif request.method == 'POST':
        for plaid_env in ('sandbox', 'development', 'production'):
            title = request.form.get(f'{plaid_env}_spreadsheet_name')
            if title:
                spreadsheet_id = create_spreadsheet(title)
                session['user_settings'][f'{plaid_env}_spreadsheet_id'] = spreadsheet_id
                session.modified = True
        return redirect(url_for('manage_spreadsheets'))
    else:
        raise ValueError('Invalid request method')

@app.route('/manage-plaid-items')
def manage_plaid_items():
    link_token = request_link_token()
    if not link_token:
        return f"""
        An error occurred when authenticating with Plaid. Make sure that you whitelist the
        following redirect URI in the
        <a href="https://dashboard.plaid.com/team/api" target="_blank">Plaid Dashboard</a>.<br>
        <samp>{url_for('plaid_oauth_callback', _external=True)}</samp>
        <br><br>
        """
    session['plaid_link_token'] = link_token
    access_tokens = (get_plaid_items()).values()
    item_info = get_plaid_item_info(access_tokens)
    return render_template('plaid_items_form.html', plaid_link_token=link_token,
        plaid_oauth_redirect=False, plaid_items=item_info)

@app.route('/plaid-oauth-callback')
def plaid_oauth_callback():
    if 'plaid_link_token' not in session:
        return redirect(url_for('manage_plaid_items'))
    link_token = session['plaid_link_token']
    del session['plaid_link_token']
    session.modified = True
    return render_template('plaid_items_form.html', plaid_link_token=link_token,
        plaid_oauth_redirect=True)


@app.route('/plaid-link-success')
def plaid_link_success():
    public_token = request.args.get('public_token')
    item_id, access_token = item_public_token_exchange(public_token)
    save_plaid_tokens(item_id, access_token)
    return redirect(url_for('manage_plaid_items'))

@app.route('/sync')
def sync():
    if not user_allowed_sync():
        print('User not allowed to sync more than once every 12 hours.')
        return redirect(url_for('index'))
    num_days = request.args.get('days', default=30, type=int)
    gsheets_service = build_gsheets_service()
    plaid_client = build_plaid_client()
    plaid_access_tokens = (get_plaid_items()).values()
    plaid_env = session['user_settings']['plaid_env']
    spreadsheet_id = session['user_settings'][f'{plaid_env}_spreadsheet_id']
    sync_transactions(gsheets_service, plaid_client, plaid_access_tokens, spreadsheet_id, num_days)
    log_user_sync()
    push_current_user()
    return redirect(url_for('index'))

def user_allowed_sync() -> bool:
    user_settings = get_current_user()
    last_sync = user_settings.get('last_sync')
    if not last_sync:
        return True
    last_sync = datetime.strptime(last_sync, TIMESTAMP_FORMAT)
    interval = timedelta(hours=12)
    if last_sync + interval < datetime.now():
        return True
    return False

def log_user_sync():
    session['user_settings']['last_sync'] = datetime.now().strftime(TIMESTAMP_FORMAT)
    session.modified = True

def get_current_user():
    return get_user(session['user_info']['sub'])

def get_user(user_id: str):
    if 'user_settings' in session and 'user_settings_ttl' in session:
        if datetime.now() < datetime.strptime(session['user_settings_ttl'], TIMESTAMP_FORMAT):
            return session['user_settings']
    document = db.collection('users').document(user_id).get()
    if document.exists:
        session['user_settings'] = document.to_dict()
    else:
        session['user_settings'] = {}
    session['user_settings_ttl'] = datetime.strftime(datetime.now() + timedelta(minutes=30), TIMESTAMP_FORMAT)
    return session['user_settings']

def push_current_user():
    db.collection('users').document(session['user_info']['sub']).set(session['user_settings'])

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

def validate_user_set_plaid_credentials() -> bool:
    user_settings = get_current_user()
    plaid_env = user_settings.get('plaid_env')
    return validate_plaid_credentials(plaid_env, user_settings.get('plaid_client_id'), user_settings.get(f'plaid_secret_{plaid_env}'))

def validate_spreadsheet_exists() -> bool:
    user_settings = get_current_user()
    plaid_env = user_settings.get('plaid_env')
    if plaid_env not in ('sandbox', 'development', 'production'):
        return False
    spreadsheet_name = lookup_spreadsheet_name_for_env(plaid_env)
    return spreadsheet_name != ''

def get_google_credentials() -> dict | None:
    user_settings = get_current_user()
    return user_settings.get('google_credentials', None)

def validate_google_credentials() -> bool:
    raw_credentials = get_google_credentials()
    if not raw_credentials:
        return False
    credentials = Credentials.from_authorized_user_info(raw_credentials)
    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(GoogleRequest())
            session['user_settings']['google_credentials'] = json.loads(credentials.to_json())
            session.modified = True
        except RefreshError: # Refresh token expired
            return False
    if not credentials.valid:
        return False
    return True

def validate_plaid_access_tokens() -> bool:
    plaid_items = get_plaid_items()
    if len(plaid_items) == 0:
        return None
    plaid_client = build_plaid_client()
    for access_token in plaid_items.values():
        try:
            plaid_client.item_get(ItemGetRequest(access_token))
        except PlaidApiException:
            return False
    return True

def get_plaid_items() -> dict[str, str]:
    user_settings = get_current_user()
    plaid_items = user_settings.get('plaid_items', {})
    plaid_env = user_settings.get('plaid_env', 'none').lower()
    result = {k: v for k, v in plaid_items.items() if v.lower().startswith(f'access-{plaid_env}')}
    return result

def lookup_spreadsheet_name(spreadsheet_id: str) -> str:
    if not spreadsheet_id:
        return ''
    gsheets_service = build_gsheets_service()
    result = gsheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return result['properties']['title']

def lookup_spreadsheet_name_for_env(plaid_env: str) -> str:
    if plaid_env not in ('sandbox', 'development', 'production'):
        raise ValueError(plaid_env)
    user_settings = get_current_user()
    try:
        spreadsheet_name = lookup_spreadsheet_name(user_settings.get(f'{plaid_env}_spreadsheet_id'))
    except googleapiclient.errors.HttpError:
        del session['user_settings'][f'{plaid_env}_spreadsheet_id']
        session.modified = True
        spreadsheet_name = ''
    return spreadsheet_name


def create_spreadsheet(title: str) -> str:
    gsheets_service = build_gsheets_service()
    spreadsheet_id = create_new_spreadsheet(gsheets_service, title)
    return spreadsheet_id

def build_gsheets_service() -> googleapiclient.discovery.Resource:
    raw_credentials = get_google_credentials()
    if not raw_credentials:
        raise KeyError('Expected to find Google credentials')
    credentials = Credentials.from_authorized_user_info(raw_credentials, GOOGLE_SCOPES)
    gsheets_service = generate_gsheets_service(credentials)
    return gsheets_service

def fetch_spreadsheet_url() -> str:
    spreadsheet_exists = validate_spreadsheet_exists()
    if spreadsheet_exists:
        gsheets_service = build_gsheets_service()
        plaid_env = session['user_settings']['plaid_env']
        spreadsheet_id = session['user_settings'][f'{plaid_env}_spreadsheet_id']
        spreadsheet_url = get_spreadsheet_url(gsheets_service, spreadsheet_id)
    else:
        spreadsheet_url = None
    return spreadsheet_url

def request_link_token() -> str:
    plaid_client = build_plaid_client()
    request = LinkTokenCreateRequest(
        products=[Products('transactions')],
        client_name="GSheets-Plaid",
        country_codes=[CountryCode('US')],
        redirect_uri=url_for('plaid_oauth_callback', _external=True),
        language='en',
        link_customization_name='default',
        user=LinkTokenCreateRequestUser(
            client_user_id=session['user_info']['sub']
        ))
    try:
        response = plaid_client.link_token_create(request)
        link_token = response['link_token']
    except PlaidApiException as e:
        print(e)
        link_token = None
    return link_token

def request_link_update_token(access_token: str) -> str:
    plaid_client = build_plaid_client()
    request = LinkTokenCreateRequest(
        client_name="GSheets-Plaid",
        country_codes=[CountryCode('US')],
        redirect_uri=url_for('plaid_oauth_callback', _external=True),
        language='en',
        link_customization_name='default',
        user=LinkTokenCreateRequestUser(
            client_user_id=session['user_info']['sub']
        ),
        access_token=access_token)
    try:
        response = plaid_client.link_token_create(request)
        link_token = response['link_token']
    except PlaidApiException as e:
        print(e)
        link_token = None
    return link_token

def build_plaid_client() -> plaid_api.PlaidApi:
    global plaid_client
    if plaid_client is not None:
        return plaid_client
    user_settings = get_current_user()
    plaid_env = user_settings.get('plaid_env')
    if plaid_env not in ('sandbox', 'development', 'production'):
        raise ValueError(plaid_env)
    plaid_client_id = user_settings.get('plaid_client_id')
    plaid_secret = user_settings.get(f'plaid_secret_{plaid_env}')
    if not validate_plaid_credentials(plaid_env, plaid_client_id, plaid_secret):
        raise ValueError('Invalid Plaid credentials')
    plaid_client = generate_plaid_client(plaid_env, plaid_client_id, plaid_secret)
    return plaid_client

def item_public_token_exchange(public_token) -> tuple[str, str]:
    plaid_client = build_plaid_client()
    request = ItemPublicTokenExchangeRequest(public_token=public_token)
    response = plaid_client.item_public_token_exchange(request)
    access_token = response['access_token']
    item_id = response['item_id']
    return item_id, access_token

def save_plaid_tokens(item_id: str, access_token: str):
    user_settings = get_current_user()
    items = user_settings.get('plaid_items', {})
    items[item_id] = access_token
    session['user_settings']['plaid_items'] = items
    session.modified = True

def get_plaid_item_info(access_tokens: list) -> tuple:
    results = []
    plaid_client = build_plaid_client()
    for token in access_tokens:
        try:
            response = plaid_client.item_get(ItemGetRequest(token))
            ins_id = response['item']['institution_id']
            ins_request = InstitutionsGetByIdRequest(ins_id, [CountryCode('US')])
            response = plaid_client.institutions_get_by_id(ins_request)
            link_update_token = request_link_update_token(token)
            results.append((response['institution']['name'], True, link_update_token))
        except PlaidApiException as e:
            raise e
    return results

@app.route('/revoke-google-credentials')
def revoke():
    raw_credentials = get_google_credentials()
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

if __name__ == '__main__':
    app.run(host='localhost', port=8080, debug=True, load_dotenv=True, ssl_context='adhoc')
