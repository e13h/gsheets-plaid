# Tutorial
Follow this guide to get the GSheets-Plaid web server running on your local machine.

Prerequisites:
  * A Google account
  * A [Plaid](https://dashboard.plaid.com/signup) account
  * Python 3.10 or higher
  * `gsheets-plaid` installed
    ```
    python3 -m pip install gsheets-plaid
    ```

## Create a new Google Cloud Project
1. Go to the [**Manage resources**](https://console.cloud.google.com/cloud-resource-manager?walkthrough_id=resource-manager--create-project&_ga=2.155866301.763359671.1663352190-792365341.1663020331) page in the Google Cloud console.
1. On the **Select organization** drop-down list at the top of the page, select the organization resource in which you want to create a project. If you are a free trial user, skip this step, as this list does not appear.
1. Click **Create Project**.
1. In the **New Project** window that appears, enter a project name and select a billing account as applicable. A project name can contain only letters, numbers, single quotes, hyphens, spaces, or exclamation points, and must be between 4 and 30 characters.
1. Enter the parent organization or folder resource in the **Location** box. That resource will be the hierarchical parent of the new project. If **No organization** is an option, you can select it to create your new project as the top level of its own resource hierarchy.
1. When you're finished entering new project details, click **Create**.

## Enable APIs
Enable the following APIs:
  * Google Sheets API
  * Cloud Run API

1. In the Google Cloud console, go to the [APIs & services Library](https://console.cloud.google.com/apis/library) for your project.
    * At the top-left, click **Menu** > **APIs & Services** > **Library**
1. Search for the API in the search bar.
1. Select the corresponding result.
1. Click **Enable**.
1. Repeat these steps until all required APIs are enabled.

## Set up the OAuth consent screen
1. In the Google Cloud console, go to the [APIs & services OAuth consent screen page](https://console.cloud.google.com/apis/credentials/consent) for your project.
    * At the top-left, click **Menu** > **APIs & Services** > **OAuth consent screen**
1. Select **External**
1. Fill out the required fields in the form.
    * App name: choose a name you like.
    * User support email: you can put your own email address.
    * Developer contact information: you can put your own email address again.
1. Click **Save and Continue**.
1. Click **Add or Remove Scopes**.
1. Add the following scopes (tip: use the filter search bar to narrow the results):
    * `https://www.googleapis.com/auth/drive.file`
1. Click **Save and Continue**.
1. Click **Add Users**.
1. Add yourself as a test user (enter an @gmail.com address that you own).
1. Click **Add**.
1. Click **Save and Continue**.
1. Review the information, then click **Back to Dashboard**.

## Prepare environment variables
In order to spin up the local web server, we need to pass in several environment variables. To make things easier, we'll record the data in a script for easy reference.

1. Create a new file named `run_web_server.sh`.
1. Add executable permissions to the script.
   ```
   chmod +x run_web_server.sh
   ```
1. Using your favorite text editor, paste in the following template as the contents of `run_web_server.sh`:
```shell
# Command for spinning up gsheets_plaid local web server
GOOGLE_CLOUD_CLIENT_ID= \
GOOGLE_CLOUD_CLIENT_CONFIG= \
GOOGLE_APPLICATION_CREDENTIALS= \
FLASK_SECRET_KEY= \
python3 -m gsheets_plaid
```

## Create OAuth client ID credentials
1. In the Google Cloud console, go to the [APIs & services Credentials page](https://console.cloud.google.com/apis/credentials) for your project.
    * At the top-left, click **Menu** > **APIs & Services** > **Credentials**
1. Click **Create Credentials** > **OAuth client ID**.
1. For **Application type**, select **Web application**.
1. Under **Authorized JavaScript Origins**, add the following URIs:
    * `https://localhost`
    * `https://localhost:8080`
1. Under **Authorized Redirect URIs**, add the following URI:
    * `https://localhost/google-oauth-callback`
1. Click **Create**.
1. In the popup that appears, copy the value in **Your Client ID** and paste it in your script as the value for `GOOGLE_CLOUD_CLIENT_ID`.
    * Note: If the popup didn't appear for some reason, or if you have previously created an OAuth Client ID, click the download icon on the corresponding ID
1. Click **Download JSON**
1. Click **OK**.
1. Enter the filepath for this JSON file you just downloaded in your script as the value for `GOOGLE_CLOUD_CLIENT_CONFIG`.

At this point, your script should look something like this:
```shell
# Command for spinning up gsheets_plaid local web server
GOOGLE_CLOUD_CLIENT_ID=123456789-abcdefghijk123456789.apps.googleusercontent.com \
GOOGLE_CLOUD_CLIENT_CONFIG=/Users/<you>/Downloads/client_secret_123456789-abcdefghijk123456789.apps.googleusercontent.com.json \
GOOGLE_APPLICATION_CREDENTIALS= \
FLASK_SECRET_KEY= \
python3 -m gsheets_plaid
```

## Create a key for the default compute service account
1. In the Google Cloud console, go to the [APIs & services Credentials page](https://console.cloud.google.com/apis/credentials) for your project.
    * At the top-left, click **Menu** > **APIs & Services** > **Credentials**
1. In the **Service Accounts** section, select the edit icon for the Default Compute Service Account.
1. Click **Keys**.
1. Select **Add Key** > **Add new key**.
1. Select JSON as the key type, then click **Create**.
1. The file should download automatically.
1. Enter the filepath for this JSON file in your script as the value for `GOOGLE_APPLICATION_CREDENTIALS`.

Now your script should look like this:
```shell
# Command for spinning up gsheets_plaid local web server
GOOGLE_CLOUD_CLIENT_ID=123456789-abcdefghijk123456789.apps.googleusercontent.com \
GOOGLE_CLOUD_CLIENT_CONFIG=/Users/<you>/Downloads/client_secret_123456789-abcdefghijk123456789.apps.googleusercontent.com.json \
GOOGLE_APPLICATION_CREDENTIALS=/Users/<you>/Downloads/project-name-123456-abcdefg12345678.json \
FLASK_SECRET_KEY= \
python3 -m gsheets_plaid
```

## Generate a random secret key
The GSheets-Plaid web server uses the [Flask](https://flask.palletsprojects.com/en/2.2.x/) micro web framework. In order to store a cookie, Flask requires you to provide a secret key that is used to cryptographically sign the cookie, so that bad actors can't edit the data in the cookie.

An easy way to get a random string that we can use as a secret key is to run this command:
```shell
python -c 'import secrets; print(secrets.token_hex())'
```
The output will be a random string of letters and numbers, like this:
```
f15e697ad4c9480c385867699152a52ba8a70ee0f70382999989d7924ae23f76
```
Generate a secret key and save it in your script as the value for `FLASK_SECRET_KEY`.

Your script should now look like this:
```shell
# Command for spinning up gsheets_plaid local web server
GOOGLE_CLOUD_CLIENT_ID=123456789-abcdefghijk123456789.apps.googleusercontent.com \
GOOGLE_CLOUD_CLIENT_CONFIG=/Users/<you>/Downloads/client_secret_123456789-abcdefghijk123456789.apps.googleusercontent.com.json \
GOOGLE_APPLICATION_CREDENTIALS=/Users/<you>/Downloads/project-name-123456-abcdefg12345678.json \
FLASK_SECRET_KEY=f15e697ad4c9480c385867699152a52ba8a70ee0f70382999989d7924ae23f76 \
python3 -m gsheets_plaid
```

## Register the Plaid redirect URI
If you haven't signed up already, [create a Plaid developer account](https://dashboard.plaid.com/signup).

Add the redirect URI `https://localhost:8080/google-oauth-callback` to the [list of allowed redirect URIs in the Plaid Dashboard](https://dashboard.plaid.com/team/api) (**Team Settings** > **API** > **Allowed redirect URIs** > **Configure**).

## Spin up the web server
Now we can run the web server script.
```
./run_web_server.sh
```
Once you sign in with your email that you whitelisted as a test user, you should see a checklist of items to complete before syncing your transactions.

Some things to note:
 * When adding bank accounts, if you are using the `sandbox` environment, note that the bank account credentials are provided at the bottom of the screen. If you are using the `development` environment, use your actual bank account credentials.
 * In the `development` environment, you are only given 5 tokens to use. If you submit a ticket on the Plaid Dashboard you can get it bumped up to 100 tokens, which should be more than plenty for personal usage.
 * Once you have added all the bank accounts you want you can close the browser tab and enter `CTRL+C` in the terminal to kill the web server process.

That's it! 🎉 Hopefully you're inspired to write some cool formulas and make neat charts using this raw transaction data.
