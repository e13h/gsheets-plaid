import json
import webbrowser
from datetime import datetime, timedelta
from importlib.resources import files

import numpy as np
import pandas as pd
import plaid
from plaid.api import plaid_api
from plaid.model.country_code import CountryCode
from plaid.model.institutions_get_by_id_request import InstitutionsGetByIdRequest
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.transactions_get_request_options import TransactionsGetRequestOptions

from gsheets_plaid.create_sheet import get_spreadsheet_id, gsheets_service
from gsheets_plaid.initialization import CONFIG

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


def generate_plaid_client() -> plaid_api.PlaidApi:
    if CONFIG.get('PLAID_ENV') == 'sandbox':
        host = plaid.Environment.Sandbox
        secret = CONFIG.get('PLAID_SECRET_SANDBOX')
    elif CONFIG.get('PLAID_ENV') == 'development':
        host = plaid.Environment.Development
        secret = CONFIG.get('PLAID_SECRET_DEVELOPMENT')
    elif CONFIG.get('PLAID_ENV') == 'production':
        host = plaid.Environment.Production
        secret = CONFIG.get('PLAID_SECRET_PRODUCTION')
    else:
        host = plaid.Environment.Sandbox
        secret = CONFIG.get('PLAID_SECRET_SANDBOX')

    plaid_config = plaid.Configuration(
        host=host,
        api_key={
            'clientId': CONFIG.get('PLAID_CLIENT_ID'),
            'secret': secret,
            'plaidVersion': '2020-09-14',
        }
    )

    api_client = plaid.ApiClient(plaid_config)
    plaid_client = plaid_api.PlaidApi(api_client)
    return plaid_client


def get_transactions_from_plaid(access_token: str, num_days: int = 30) -> pd.DataFrame:
    """Get transaction data from Plaid for a given access token.
    """
    client = generate_plaid_client()
    start_date = (datetime.now() - timedelta(days=num_days))
    end_date = datetime.now()
    options = TransactionsGetRequestOptions(include_personal_finance_category=True)
    transaction_request = TransactionsGetRequest(
        access_token=access_token,
        start_date=start_date.date(),
        end_date=end_date.date(),
        options=options
    )
    transaction_response = client.transactions_get(transaction_request)
    transactions = pd.DataFrame(transaction_response.to_dict().get('transactions'))[TRANSACTION_COLS]
    accounts = pd.DataFrame(transaction_response.to_dict().get('accounts'))[ACCOUNT_COLS]
    item = pd.Series(transaction_response.to_dict().get('item'))[ITEM_COLS]
    institution_request = InstitutionsGetByIdRequest(
        institution_id=item.institution_id,
        country_codes=list(map(lambda x: CountryCode(x), ['US']))
    )
    institution_response = client.institutions_get_by_id(institution_request)
    institution = pd.Series(institution_response.to_dict().get('institution'))

    # Convert datetime to string
    def fillna_datetime(row: pd.Series) -> datetime:
        if row.datetime is not None:
            return row.datetime
        return datetime.combine(row.date, datetime.min.time())
    transactions['datetime'] = transactions.apply(fillna_datetime, axis=1)
    transactions['datetime'] = transactions['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
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

    # Expand personal finance category
    personal_finance_categories = transactions.personal_finance_category.apply(pd.Series)
    personal_finance_categories.rename(
        columns={
            'primary': 'personal_finance_category_primary',
            'detailed': 'personal_finance_category_detailed'
        }, inplace=True)

    # Combine expanded columns
    transactions = pd.concat(
        (
            transactions.drop(columns=['location', 'category', 'personal_finance_category']),
            categories,
            personal_finance_categories,
            locations,
        ), axis=1)

    # Add account info
    accounts.set_index('account_id', inplace=True)
    account_name_idx = TRANSACTION_COLS.index('account_id') + 1
    account_name = transactions.account_id.apply(lambda x: accounts.loc[x].get('name'))
    transactions.insert(account_name_idx, 'account_name', account_name)

    # Add item info
    transactions.insert(account_name_idx + 1, 'item_id', item.item_id)
    transactions.insert(account_name_idx + 2, 'institution_id', item.institution_id)
    transactions.insert(account_name_idx + 3, 'institution_name', institution.get('name'))

    return transactions


def get_transactions_from_gsheet() -> pd.DataFrame:
    """Get the transactions already saved to the Google Sheet.
    """
    result = gsheets_service.spreadsheets().values().get(
        spreadsheetId=get_spreadsheet_id(verbose=True),
        range='Sheet1',
    ).execute()
    rows = result.get('values', [])
    if not len(rows):
        return []
    transactions = pd.DataFrame(rows[1:], columns=rows[0])

    # Turn pending into a boolean column
    def convert_pending(cell: str) -> bool:
        if cell is None:
            return ''
        return cell.lower() == 'true'
    transactions['pending'] = transactions.pending.apply(convert_pending)
    return transactions


def merge_transactions(existing_transactions: pd.DataFrame, new_transactions: pd.DataFrame) -> pd.DataFrame:
    """Merge new transactions with existing transactions.
    """
    num_preexisting_rows = len(existing_transactions)
    if not num_preexisting_rows:
        return new_transactions

    # Drop pending transactions that share the same item_id as new_transactions
    current_item = existing_transactions.item_id.isin(new_transactions.item_id.unique())
    existing_transactions = existing_transactions[~(current_item & existing_transactions.pending)]

    # Drop new_transactions that are already found in existing_transactions
    new_transaction_ids = new_transactions.transaction_id
    existing_transaction_ids = existing_transactions.transaction_id
    new_transactions = new_transactions[~new_transaction_ids.isin(existing_transaction_ids)]

    # Concatenate new_transactions to existing_transactions
    result = pd.concat((existing_transactions, new_transactions), axis=0)

    # Sort
    result.sort_values(
        by=['pending', 'datetime', 'name'],
        ascending=[False, False, True],
        inplace=True,
        ignore_index=True)

    # Add (num_preexisting_rows - num_result_rows) blank rows to the result
    num_blank_rows = num_preexisting_rows - len(result)
    if num_blank_rows > 0:
        blank_rows = pd.DataFrame([[np.nan] * len(result.columns)] * num_blank_rows, columns=result.columns)
        result = pd.concat((result, blank_rows), axis=0)
    
    result.fillna('', inplace=True)
    return result


def fill_gsheet(transactions: pd.DataFrame):
    """Fill transaction data into Google Sheet.
    """
    headers = transactions.columns.tolist()
    values = transactions.fillna('').to_numpy().tolist()
    values.insert(0, headers)
    gsheets_service.spreadsheets().values().update(
        spreadsheetId=get_spreadsheet_id(),
        range='Sheet1',
        valueInputOption='USER_ENTERED',
        body={'values': values},
    ).execute()


def apply_gsheet_formatting(transactions: pd.DataFrame):
    """Apply some formatting to the Google Sheet (datetime format, freeze
    header, etc.).
    """
    datetime_format = {
        'repeatCell': {
            'range': {
                'startColumnIndex': transactions.columns.get_loc('datetime'),
                'endColumnIndex': transactions.columns.get_loc('datetime') + 1,
            },
            'cell': {
                'userEnteredFormat': {
                    'numberFormat': {
                        'type': 'DATE',
                        'pattern': 'yyyy-mm-dd hh:mm:ss'
                    }
                }
            },
            'fields': 'userEnteredFormat.numberFormat',
        }
    }
    header_format = {
        'repeatCell': {
            'range': {
                'startRowIndex': 0,
                'endRowIndex': 1,
            },
            'cell': {
                'userEnteredFormat': {
                    'textFormat': {
                        'bold': True,
                    }
                }
            },
            'fields': 'userEnteredFormat.textFormat',
        }
    }
    freeze_header = {
        'updateSheetProperties': {
            'properties': {
                'gridProperties': {
                    'frozenRowCount': 1,
                }
            },
            'fields': 'gridProperties.frozenRowCount',
        }
    }
    # Send batch requests
    requests = [
        datetime_format,
        header_format,
        freeze_header,
    ]
    gsheets_service.spreadsheets().batchUpdate(
        spreadsheetId=get_spreadsheet_id(),
        body={'requests': requests},
    ).execute()


def get_access_tokens() -> list[dict]:
    """Load the access tokens from file.
    """
    token_pkg = 'gsheets_plaid.resources.db.tokens'
    token_filename = CONFIG.get('PLAID_TOKENS_OUTPUT_FILENAME')
    token_resource = files(token_pkg).joinpath(token_filename)
    with open(token_resource, 'r') as file:
        tokens = json.load(file)
    env_str = CONFIG.get('PLAID_ENV', 'sandbox').lower()
    tokens = [token for token in tokens if token['access_token'].startswith(f'access-{env_str}')]
    return tokens


def get_spreadsheet_url() -> str:
    """Get the URL of the Google Sheet.
    """
    response = gsheets_service.spreadsheets().get(spreadsheetId=get_spreadsheet_id()).execute()
    return response.get('spreadsheetUrl')


def sync_transactions(plaid_env: str = None, num_days: int = 30):
    """Put transaction data into Google Sheet.
    """
    if plaid_env:
        CONFIG['PLAID_ENV'] = plaid_env
    result = get_transactions_from_gsheet()
    for token in get_access_tokens():
        try:
            new_transactions = get_transactions_from_plaid(token['access_token'], num_days)
            result = merge_transactions(result, new_transactions)
        except plaid.ApiException as e:
            print(e)
            continue
    fill_gsheet(result)
    apply_gsheet_formatting(result)
    webbrowser.open(get_spreadsheet_url(), new=1, autoraise=True)


if __name__ == '__main__':
    sync_transactions()
