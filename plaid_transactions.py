import json
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import plaid
from dotenv import dotenv_values
from plaid.api import plaid_api
from plaid.model.country_code import CountryCode
from plaid.model.institutions_get_by_id_request import InstitutionsGetByIdRequest
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

def get_transactions_from_plaid(access_token: str, num_days: int = 30) -> pd.DataFrame:
    """Get transaction data from Plaid for a given access token.
    """
    start_date = (datetime.now() - timedelta(days=num_days))
    end_date = datetime.now()
    try:
        options = TransactionsGetRequestOptions()
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

        # Combine expanded columns
        transactions = pd.concat(
            (
                transactions.drop(columns=['location', 'category']),
                categories,
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
    except plaid.ApiException as e:
        print(e)


def column_idx_to_str(n: int) -> str:
    NUM_LETTERS = 26
    A_ASCII = 65
    result = ''
    while n > 0:
        n, remainder = divmod(n - 1, NUM_LETTERS)
        result = chr(A_ASCII + remainder) + result
    return result


def get_transactions_from_gsheet(num_columns: int) -> pd.DataFrame:
    """Get the transactions already saved to the Google Sheet.
    """
    result = gsheets_service.spreadsheets().values().get(
        spreadsheetId=get_spreadsheet_id(),
        range=f'A1:{column_idx_to_str(num_columns)}',
    ).execute()
    rows = result.get('values', [])
    if not len(rows):
        return []
    transactions = pd.DataFrame(rows[1:], columns=rows[0])

    # Turn pending into a boolean column
    transactions['pending'] = transactions.pending.apply(lambda x: x.lower() == 'true')
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
        ascending=[True, False, True],
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
    values = transactions.to_numpy().tolist()
    values.insert(0, headers)
    gsheets_service.spreadsheets().values().update(
        spreadsheetId=get_spreadsheet_id(),
        range=f'A1:{column_idx_to_str(len(headers))}',
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
    response = gsheets_service.spreadsheets().batchUpdate(
        spreadsheetId=get_spreadsheet_id(),
        body={'requests': requests},
    ).execute()
    print(response)


def get_access_tokens() -> list[dict]:
    """Load the access tokens from file.
    """
    with open(CONFIG.get('PLAID_TOKENS_OUTPUT_FILENAME')) as file:
        tokens = json.load(file)
    return tokens


def main():
    """Put transaction data into Google Sheet.
    """
    result = get_transactions_from_gsheet(29)  # FIXME get rid of magic number
    for token in get_access_tokens():
        new_transactions = get_transactions_from_plaid(token['access_token'], num_days=30)
        result = merge_transactions(result, new_transactions)
    fill_gsheet(result)
    apply_gsheet_formatting(result)


if __name__ == '__main__':
    main()
