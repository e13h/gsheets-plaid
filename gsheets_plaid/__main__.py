import os
import threading
import webbrowser
from time import sleep

from dotenv import load_dotenv

from gsheets_plaid.web_server.main import run_web_server

load_dotenv(os.path.join(os.path.dirname(__file__), 'web_server/.env'))
t = threading.Thread(target=run_web_server, kwargs={'ssl_context': 'adhoc'})
t.start()
sleep(1)  # Wait for the server to start

# Direct the user to Plaid Link
webbrowser.open('https://localhost:8080/', new=1, autoraise=True)
t.join()
