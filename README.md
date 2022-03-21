# GSheets-Plaid sandbox
A spring break project to get my bank transaction data in Google Sheets without using Google Apps Script.

## To-do
- [x] Use the [Google Sheets Python API](https://developers.google.com/sheets/api/quickstart/python?authuser=0) to [create a new spreadsheet](https://stackoverflow.com/questions/69610443/how-do-i-use-the-drive-file-scope-for-a-standalone-google-apps-script/69611115#69611115).
- [x] Use the Plaid API to fill this new spreadsheet with sandbox data
- [ ] Use the [Google Identity API](https://developers.google.com/identity/gsi/web/guides/overview) to create a "Sign in with Google" button that creates a new spreadsheet and fills it with sandbox data from Plaid
- [ ] Turn the Python code into a `pip`-installable module
- [ ] Figure out how to deploy this onto `evanphilipsmith.com`
- [ ] Use the Plaid API to fill the spreadsheet in with actual data
