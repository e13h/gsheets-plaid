# GSheets-Plaid
A spring break project to get my bank transaction data in Google Sheets without using Google Apps Script.

`gsheets-plaid` is a tool for getting your raw bank transaction data into a Google Sheets spreadsheet, to enable you to make your own formulas and charts for tracking spending, making goals, etc. This app is 100% free (assuming you don't already have a bunch of Google Cloud projects), but there is a bit of one-time setting up to do to get your Google and Plaid credentials in place. This README contains all the instructions to get you from a fresh install of the package to bank transactions in a Google Sheets file.

Please open an issue if something isn't working or if the documentation isn't clear.

## Usage
### Prerequisites
* Python 3.10 or later

### Installation
Using a virtualenv is a good idea.
```shell
python3 -m pip install gsheets-plaid
```

### Create a Google Cloud project and enable the Google Sheets API
Follow [this tutorial](https://developers.google.com/workspace/guides/create-project?authuser=0)

**Be sure to enable the "Google Sheets API"**

### Create access credentials for Google
Follow [this tutorial](https://developers.google.com/workspace/guides/create-credentials?authuser=0#oauth-client-id) for creating OAuth client ID credentials for your Google account.

* Choose "Desktop app" in the tutorial
#### OAuth consent screen
Before Google Cloud Platform will let you create OAuth client ID credentials, it will make you complete the OAuth consent screen.
Fill out the required fields with your personal email, and choose an arbitrary application name. Since we aren't planning on publishing this app, it doesn't really matter.

On the "Scopes" step, add the following scope: `https://www.googleapis.com/auth/drive.file`. You can use the search feature and look up `drive.file` to quickly find the right scope.

On the "Test users" page, add the google account email that corresponds with the account you want to have the finance tracker saved on.

#### Back to creating OAuth credentials
Here is a summary of how to create the credentials:
1. Click "Create credentials"
2. Click "OAuth client ID"
3. Select "Desktop app"
4. Type a name of your choice
5. Click the download icon (when you hover it says "Download OAuth Client")
6. Click "Download JSON"

### Create a Plaid Developer account
Create a Plaid developer account [here](https://dashboard.plaid.com/signup).

After you have created an account, go to Team Settings > Keys. You should see your `client_id`, as well as Development and Sandbox secrets.

#### Register the redirect URI in the Plaid Dashboard
Add the redirect URI to the [list of allowed redirect URIs in the Plaid Dashboard](https://dashboard.plaid.com/team/api). By default, the redirect URI is `https://localhost:8080/google-oauth-callback`.

### Link a bank account
We are finally getting to the exciting part!

If everything is configured correctly, running the following command will open a new browser tab with a small local web server you can use to connect a bank account.
```shell
python3 -m gsheets_plaid
```
If you are using the `sandbox` environment, note that the credentials are provided at the bottom of the screen. If you are using the `development` environment, use your actual bank account credentials. Note that you are only given 5 tokens to use in the development environment, but if you submit a ticket on Plaid Dashboard, you can get it bumped up to 100 tokens, which should be more than plenty for personal usage.

Once you have added all the bank accounts you want, close the browser tab and enter `CTRL+C` in the terminal you started the `link` command in to kill the web server process.

That's it! Hopefully you're inspired to write some cool formulas and make neat charts using this raw transaction data.

---

## Publishing new releases
(for maintainers)

1. Tag the main branch
```
git tag v[insert-version-here]
```
2. Push latest commits with tags
```
git push origin --tags
```
3. Build repo
```
python -m build
```
4. Upload distribution archives to PyPi
```
python -m twine upload dist/*
```
5. Create new release on GitHub
