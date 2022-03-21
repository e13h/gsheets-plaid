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
TRANSACTION_COLS = [
    'transaction_id',
    'pending_transaction_id',
    'pending',
    'account_id',
    'date',
    'datetime',
    'name',
    'merchant_name',
    'amount',
    'iso_currency_code',
    'unofficial_currency_code',
    'payment_channel',
    'category_id',
    'category',
    'personal_finance_category',
    'location',
]
ACCOUNT_COLS = [
    'account_id',
    'balances',
    'name',
    'type',
    'subtype',
]
ITEM_COLS = [
    'item_id',
    'institution_id',
    'consent_expiration_time',
]

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
        transactions = pd.DataFrame(response.to_dict().get('transactions'))[TRANSACTION_COLS]
        accounts = pd.DataFrame(response.to_dict().get('accounts'))[ACCOUNT_COLS]
        item = pd.Series(response.to_dict().get('item'))[ITEM_COLS]

        # Convert datetime to string
        def fillna_datetime(row: pd.Series) -> datetime:
            if row.datetime is not None:
                return row.datetime
            return datetime.combine(row.date, datetime.min.time())
        transactions['datetime'] = transactions.apply(fillna_datetime, axis=1)
        transactions['datetime'] = transactions['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S%Z')
        transactions['date'] = transactions['date'].astype(str)

        # Expand categories
        categories = (
            transactions
            .category
            .apply(pd.Series)
            .fillna('')
            .rename(columns={0: 'category1', 1: 'category2', 2: 'category3'}))

        # Expand location
        locations = transactions.location.apply(pd.Series)

        # Combine expanded columns
        transactions = pd.concat(
            (
                transactions.drop(columns=['location', 'category']),
                categories,
                locations,
            ), axis=1)

        # Add account info
        accounts.set_index('account_id', inplace=True)
        transactions['account_name'] = transactions.account_id.apply(lambda x: accounts.loc[x].get('name'))

        # Add item info
        transactions['item_id'] = item.item_id
        transactions['institution_id'] = item.institution_id

        transactions.set_index('transaction_id', drop=False, inplace=True)
        headers = transactions.columns.tolist()
        values = transactions.to_numpy().tolist()
        values.insert(0, headers)
        return values
    except plaid.ApiException as e:
        print(e)


def fill_gsheet(transactions: list[list]):
    """Fill transaction data into Google Sheet.
    """
    gsheets_service.spreadsheets().values().append(
        spreadsheetId=get_spreadsheet_id(),
        range='A1:AB',
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
