
import shutil
from importlib.resources import files
from textwrap import dedent

from dotenv import dotenv_values, set_key
from plaid.exceptions import ApiException

DB_PACKAGE = 'gsheets_plaid.resources.db'
ENV_RESOURCE = files(DB_PACKAGE).joinpath('.env')
if not ENV_RESOURCE.is_file():
    TEMPLATE_ENV_RESOURCE = files(DB_PACKAGE).joinpath('.env.example')
    shutil.copyfile(TEMPLATE_ENV_RESOURCE, ENV_RESOURCE)
CONFIG = dotenv_values(ENV_RESOURCE)


def is_initialized():
    token_pkg = 'gsheets_plaid.resources.db.tokens'
    creds_filename = CONFIG.get('GOOGLE_CREDENTIAL_FILENAME')
    creds_resource = files(token_pkg).joinpath(creds_filename)
    if not creds_resource.is_file():
        return False
    if CONFIG.get('PLAID_ENV', None) == 'sandbox':
        required_key = 'PLAID_SECRET_SANDBOX'
    elif CONFIG.get('PLAID_ENV', None) == 'development':
        required_key = 'PLAID_SECRET_DEVELOPMENT'
    elif CONFIG.get('PLAID_ENV', None) == 'production':
        required_key = 'PLAID_SECRET_PRODUCTION'
    else:
        required_key = 'PLAID_SECRET_SANDBOX'
    initialized = CONFIG.get('PLAID_CLIENT_ID', None) and CONFIG.get(required_key, None)
    return initialized


def initialize():
    update_exposed_env_variables()
    save_credentials()

    # Reload the redirect URI (will be different if port was changed)
    CONFIG['PLAID_SANDBOX_REDIRECT_URI'] = dotenv_values(ENV_RESOURCE)['PLAID_SANDBOX_REDIRECT_URI']
    try:
        from gsheets_plaid.resources.plaid_link_server.server import request_link_token
        request_link_token()
    except ApiException:
        msg = f"""
        The Plaid redirect URI is {CONFIG["PLAID_SANDBOX_REDIRECT_URI"]}
        Make sure this is set in your Plaid Dashboard!
        """
        print(dedent(msg))


def update_exposed_env_variables():
    def user_set_key(env_variable: str) -> str:
        description = env_variable.replace('_', ' ').title()
        existing_value = CONFIG.get(env_variable, '')
        prompt = f'{description} [{existing_value}]: '
        value = input(prompt)
        if not value:  # User just pressed enter (keep existing value)
            return
        if not value.strip():  # User entered whitespace (clear the value)
            value = ''
        # User entered a value (use that value)
        set_key(ENV_RESOURCE, env_variable, value, quote_mode='auto')
        CONFIG[env_variable] = value

    print('Enter the following values. Leave blank to keep the existing value.')
    print('Submit a space or tab to clear the value.')
    print('Plaid secrets not corresponding to the current environment are not required.')
    print()
    print('Parameter to set [existing value]: ')
    user_set_key('PLAID_CLIENT_ID')
    user_set_key('PLAID_SECRET_SANDBOX')
    user_set_key('PLAID_SECRET_DEVELOPMENT')
    user_set_key('PLAID_SECRET_PRODUCTION')
    user_set_key('PLAID_ENV')
    user_set_key('PLAID_LINK_PORT')


def save_credentials():
    """Ask the user for the Google Credentials JSON file and save it.
    """
    saved = False
    while not saved:
        token_pkg = 'gsheets_plaid.resources.db.tokens'
        creds_filename = CONFIG.get('GOOGLE_CREDENTIAL_FILENAME')
        creds_resource = files(token_pkg).joinpath(creds_filename)
        creds_exist = creds_resource.is_file()
        found = "Existing creds found" if creds_exist else "No creds found"
        prompt = f'Enter the path to the Google Credentials JSON file [{found}]: '
        filepath = input(prompt)
        if not filepath.strip():
            return
        try:
            shutil.copyfile(filepath, creds_resource)
            saved = True
        except FileNotFoundError:
            print('File not found. Please try again.')
    print('Credentials saved.')
