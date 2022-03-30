
import os
import shutil
from dotenv import dotenv_values, set_key

DOTENV_PATH = 'db/.env'
if not os.path.exists(DOTENV_PATH):
    shutil.copyfile('db/.env.example', DOTENV_PATH)

CONFIG = dotenv_values(DOTENV_PATH)


def is_initialized():
    if not os.path.exists(CONFIG.get('GOOGLE_CREDENTIAL_FILENAME')):
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


def update_exposed_env_variables():
    def user_set_key(env_variable: str) -> str:
        description = env_variable.replace('_', ' ').title()
        existing_value = CONFIG.get(env_variable, '')
        prompt = f'{description} [{existing_value}]: '
        value = input(prompt)
        if not value:  # User just pressed enter (keep existing value)
            return
        if not value.strip():  # User entered whitespace (clear the value)
            value = None
        # User entered a value (use that value)
        set_key(DOTENV_PATH, env_variable, value, quote_mode='auto')

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
    user_set_key('PLAID_SANDBOX_REDIRECT_URI')
    user_set_key('PLAID_LINK_PORT')


def save_credentials():
    """Ask the user for the Google Credentials JSON file and save it.
    """
    saved = False
    while not saved:
        creds_exist = os.path.exists(CONFIG.get('GOOGLE_CREDENTIAL_FILENAME'))
        found = "Existing creds found" if creds_exist else "No creds found"
        prompt = f'Enter the path to the Google Credentials JSON file [{found}]: '
        filepath = input(prompt)
        if not filepath.strip():
            return
        try:
            shutil.copyfile(filepath, CONFIG.get('GOOGLE_CREDENTIAL_FILENAME'))
            saved = True
        except FileNotFoundError:
            print('File not found. Please try again.')
    print('Credentials saved.')
