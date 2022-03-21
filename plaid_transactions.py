import json
from datetime import datetime, timedelta

import pandas as pd
import plaid
from dotenv import dotenv_values
from plaid.api import plaid_api
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.transactions_get_request_options import TransactionsGetRequestOptions

from create_sheet import get_spreadsheet_id, gsheets_service

CONFIG = dotenv_values('.env')

if CONFIG.get('PLAID_ENV') == 'sandbox':
    host = plaid.Environment.Sandbox
elif CONFIG.get('PLAID_ENV') == 'development':
    host = plaid.Environment.Development
elif CONFIG.get('PLAID_ENV') == 'production':
    host = plaid.Environment.Production
else:
    host = plaid.Environment.Sandbox

plaid_config = plaid.Configuration(
    host=host,
    api_key={
        'clientId': CONFIG.get('PLAID_CLIENT_ID'),
        'secret': CONFIG.get('PLAID_SECRET'),
        'plaidVersion': '2020-09-14',
    }
)

api_client = plaid.ApiClient(plaid_config)
client = plaid_api.PlaidApi(api_client)

def get_transaction_data(access_token: str, num_days: int = 30):
    """Get transaction data from Plaid for a given access token.
    """
    start_date = (datetime.now() - timedelta(days=num_days))
    end_date = datetime.now()
    try:
        options = TransactionsGetRequestOptions()
        request = TransactionsGetRequest(
            access_token=access_token,
            start_date=start_date.date(),
            end_date=end_date.date(),
            options=options
        )
        response = client.transactions_get(request)
        cols = ['transaction_id', 'account_id', 'merchant_name', 'name', 'amount', 'date']#, 'category']
        transactions = pd.DataFrame(response.to_dict().get('transactions'))
        transactions['date'] = transactions['date'].astype(str)
        return transactions[cols].to_numpy().tolist()
    except plaid.ApiException as e:
        print(e)


def fill_gsheet(transactions: list[list]):
    """Fill transaction data into Google Sheet.
    """
    gsheets_service.spreadsheets().values().append(
        spreadsheetId=get_spreadsheet_id(),
        range='A2:Z',
        valueInputOption='USER_ENTERED',
        body={'values': transactions},
    ).execute()


def get_access_tokens() -> list[dict]:
    """Load the access tokens from file.
    """
    with open(CONFIG.get('PLAID_TOKENS_OUTPUT_FILENAME')) as file:
        tokens = json.load(file)
    return tokens


def main():
    """Put transaction data into Google Sheet.
    """
    for token in get_access_tokens():
        fill_gsheet(get_transaction_data(token['access_token'], num_days=30))
        break

if __name__ == '__main__':
    main()
