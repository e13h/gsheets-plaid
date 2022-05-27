import json
import os
from importlib.resources import files

import plaid
from flask import Flask, redirect, render_template, request, url_for
from gsheets_plaid.initialization import CONFIG
from plaid.api import plaid_api
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products


class LazyPlaidClient:
    client = None
    
    def __getattr__(self, name):
        if self.client is None:
            self.load_client()
        return getattr(self.client, name)

    def load_client(self):
        if CONFIG['PLAID_ENV'] == 'sandbox':
            host = plaid.Environment.Sandbox
            secret = CONFIG['PLAID_SECRET_SANDBOX']
        elif CONFIG['PLAID_ENV'] == 'development':
            host = plaid.Environment.Development
            secret = CONFIG['PLAID_SECRET_DEVELOPMENT']
        elif CONFIG['PLAID_ENV'] == 'production':
            host = plaid.Environment.Production
            secret = CONFIG['PLAID_SECRET_PRODUCTION']
        else:
            host = plaid.Environment.Sandbox
            secret = CONFIG['PLAID_SECRET_SANDBOX']

        configuration = plaid.Configuration(
            host=host,
            api_key={
                'clientId': CONFIG['PLAID_CLIENT_ID'],
                'secret': secret,
                'plaidVersion': '2020-09-14'
            }
        )

        api_client = plaid.ApiClient(configuration)
        client = plaid_api.PlaidApi(api_client)
        self.client = client

client = LazyPlaidClient()

app = Flask(__name__)

@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html', plaid_link_token=request_link_token(),
        plaid_link_port=CONFIG['PLAID_LINK_PORT'])

@app.route('/oauth')
def oauth():
    return render_template('oauth.html')

@app.route('/success')
def success():
    public_token = request.args.get('public_token')
    item_id, access_token = item_public_token_exchange(public_token)
    save_tokens(item_id, access_token)
    return redirect(url_for('index'))


def request_link_token():
    request = LinkTokenCreateRequest(
        products=[Products('transactions')],
        client_name="Plaid Test App",
        country_codes=[CountryCode('US')],
        redirect_uri=CONFIG['PLAID_SANDBOX_REDIRECT_URI'],
        language='en',
        link_customization_name='default',
        user=LinkTokenCreateRequestUser(
            client_user_id='123-test-user-id'
        )
    )
    # create link token
    response = client.link_token_create(request)
    link_token = response['link_token']
    return link_token

def item_public_token_exchange(public_token) -> tuple[str, str]:
    request = ItemPublicTokenExchangeRequest(public_token=public_token)
    response = client.item_public_token_exchange(request)
    access_token = response['access_token']
    item_id = response['item_id']
    return item_id, access_token

def save_tokens(item_id, access_token):
    token_pkg = 'gsheets_plaid.resources.db.tokens'
    token_filename = CONFIG.get('PLAID_TOKENS_OUTPUT_FILENAME')
    token_resource = files(token_pkg).joinpath(token_filename)
    if not os.path.exists(token_resource):
        with open(token_resource, 'x') as file:
            json.dump([], file)
    with open(token_resource, 'r') as file:
        tokens: list = json.load(file)
    tokens.append({'item_id': item_id, 'access_token': access_token})
    with open(token_resource, 'w') as file:
        json.dump(tokens, file)


if __name__ == '__main__':
    app.run(host='localhost', port=CONFIG['PLAID_LINK_PORT'])
