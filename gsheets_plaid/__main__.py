import argparse
import sys

from gsheets_plaid.initialization import is_initialized, initialize


# Main parser
description = 'Sync transaction data to Google Sheets using Plaid.'
parser = argparse.ArgumentParser(description=description, prog='gsheets_plaid')
parser.add_argument('-v', '--verbose', action='store_true', help='print verbose output')
subparsers = parser.add_subparsers(dest='action', required=True, metavar='sub-command')


# Parser for the 'init' command
parser_init = subparsers.add_parser('init', help='initialize')


# Parser for the 'link' command
parser_link = subparsers.add_parser('link', help='link new accounts, manage existing accounts')
parser_link.add_argument('--port', type=int, help='port to run Plaid Link on')
parser_link.add_argument(
    '--env',
    type=str,
    choices=['sandbox', 'development', 'production'],
    help='temporarily run with a different env type (does NOT change config)')
parser_link.add_argument(
    '--redirect-uri',
    type=str,
    help='temporarily run with a different redirect URI (only affects OAuth banks, does NOT change config)')


# Parser for the 'sync' command
parser_sync = subparsers.add_parser('sync', help='sync transactions from linked accounts')
parser_sync.add_argument('--days', type=int, default=30, help='number of days to sync')

if len(sys.argv) == 1:
    parser.print_help(sys.stderr)
    sys.exit(1)


args = parser.parse_args()
if not is_initialized() and args.action != 'init':
    parser.error('Please run "gsheets_plaid init" before running any other commands.')

print(args)
if args.action == 'init':
    initialize()
