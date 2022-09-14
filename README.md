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
6. Save your Client ID for later, we will use it as the `GOOGLE_CLOUD_CLIENT_ID` environment variable
7. Click "Download JSON"

Later, we will use the OAuth credentials filepath as the `GOOGLE_CLOUD_CLIENT_CONFIG` environment variable.

### Create a Google service account key
Follow [this tutorial](https://cloud.google.com/iam/docs/creating-managing-service-account-keys#creating) for creating and downloading a service account key for the default compute service account in your Google Cloud project. Later, we will use the service account key filepath as the `GOOGLE_APPLICATION_CREDENTIALS` environment variable.

**Note**: Service account keys are sensitive and should not be shared. See [this documentation](https://cloud.google.com/docs/authentication/application-default-credentials) for alternative authentication strategies.
### Create a Plaid Developer account
Create a Plaid developer account [here](https://dashboard.plaid.com/signup).

After you have created an account, go to Team Settings > Keys. You should see your `client_id`, as well as Development and Sandbox secrets. Have these keys ready to copy for later. Once you are able to get the local web server running, you will enter them there.

#### Register the redirect URI in the Plaid Dashboard
Add the redirect URI to the [list of allowed redirect URIs in the Plaid Dashboard](https://dashboard.plaid.com/team/api). By default, the redirect URI is `https://localhost:8080/google-oauth-callback`.

### Generate a random string for cookie signing
In order to use cookies in Flask, you **must** set the `FLASK_SECRET_KEY` environment variable or it won't work. Since this project isn't designed to be production-ready, you can use literally any string of text, or for best practice you can run some kind of cryptographic random generator.

See [this documentation](https://flask.palletsprojects.com/en/2.2.x/quickstart/?highlight=secret%20key#sessions) for more information (including examples of how to quickly generate a cryptographically random secret key).

### Link a bank account
We are finally getting to the exciting part!

If everything is configured correctly, running the following command will open a new browser tab with a small local web server you can use to connect a bank account.
```shell
GOOGLE_CLOUD_CLIENT_ID=your_google_cloud_client_id_here \
GOOGLE_CLOUD_CLIENT_CONFIG=/path/to/oauth/client/credentials/file.json \
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service/account/key.json \
FLASK_SECRET_KEY=super_secret_string \
python3 -m gsheets_plaid
```
If you are using the `sandbox` environment, note that the credentials are provided at the bottom of the screen. If you are using the `development` environment, use your actual bank account credentials. Note that you are only given 5 tokens to use in the development environment, but if you submit a ticket on Plaid Dashboard, you can get it bumped up to 100 tokens, which should be more than plenty for personal usage.

Once you have added all the bank accounts you want, close the browser tab and enter `CTRL+C` in the terminal to kill the web server process.

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
