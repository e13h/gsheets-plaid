import argparse
import sys
import webbrowser

from gsheets_plaid.data import (get_access_tokens, get_spreadsheet_id_from_file,
                                load_creds_from_file)
from gsheets_plaid.services import GOOGLE_SCOPES, generate_gsheets_service, generate_plaid_client
from gsheets_plaid.sync import get_spreadsheet_url

# Main parser
description = 'Sync transaction data to Google Sheets using Plaid.'
parser = argparse.ArgumentParser(description=description, prog='gsheets_plaid')
parser.add_argument('-v', '--verbose', action='store_true', help='print verbose output')
subparsers = parser.add_subparsers(dest='action', required=True, metavar='sub-command')


# Parser for the 'init' command
parser_init = subparsers.add_parser('init', help='initialize')


# Parser for the 'link' command
parser_link = subparsers.add_parser('link', help='link new accounts, manage existing accounts')
parser_link.add_argument(
    '--env',
    type=str,
    choices=['sandbox', 'development', 'production'],
    help='temporarily run with a different env type (does NOT change config)')


# Parser for the 'sync' command
parser_sync = subparsers.add_parser('sync', help='sync transactions from linked accounts')
parser_sync.add_argument('--days', type=int, default=30, help='number of days to sync')
parser_sync.add_argument(
    '--env',
    type=str,
    choices=['sandbox', 'development', 'production'],
    help='temporarily run with a different env type (does NOT change config)')

if len(sys.argv) == 1:
    parser.print_help(sys.stderr)
    sys.exit(1)


args = parser.parse_args()

from gsheets_plaid.initialization import CONFIG, is_initialized

if not is_initialized() and args.action != 'init':
    parser.error('Please run "gsheets_plaid init" before running any other commands.')

if args.env:
    CONFIG['PLAID_ENV'] = args.env

if args.action == 'init':
    from gsheets_plaid.initialization import initialize
    initialize()
elif args.action == 'link':
    from gsheets_plaid.link import run_link_server
    run_link_server(CONFIG['PLAID_LINK_PORT'])
elif args.action == 'sync':
    from gsheets_plaid.sync import sync_transactions
    plaid_env = CONFIG.get('PLAID_ENV')
    plaid_secret = CONFIG.get(f'PLAID_SECRET_{plaid_env.upper()}', None)
    if not plaid_secret:
        raise ValueError(f'Either {plaid_env} is incorrect or PLAID_SECRET_{plaid_env.upper()} does not exist!')
    gsheets_credentials = load_creds_from_file(GOOGLE_SCOPES)
    gsheets_service = generate_gsheets_service(gsheets_credentials)
    plaid_client = generate_plaid_client(plaid_env, CONFIG.get('PLAID_CLIENT_ID'), plaid_secret)
    access_tokens = get_access_tokens()
    spreadsheet_id = get_spreadsheet_id_from_file(gsheets_service, verbose=True)
    sync_transactions(gsheets_service, plaid_client, access_tokens, spreadsheet_id, args.days)
    webbrowser.open(get_spreadsheet_url(gsheets_service, spreadsheet_id), new=1, autoraise=True)
