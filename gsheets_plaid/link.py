import threading
import webbrowser
from time import sleep

from gsheets_plaid.initialization import CONFIG
from gsheets_plaid.resources.plaid_link_server.server import app


def run_link_server(env: str = None):
    """Run Plaid Link flow.
    """
    if env:
        CONFIG['PLAID_ENV'] = env
    t = threading.Thread(target=app.run, kwargs={'host': 'localhost', 'port': CONFIG['PLAID_LINK_PORT']})
    t.start()
    sleep(1)  # Wait for the server to start

    # Direct the user to Plaid Link
    webbrowser.open(f'http://localhost:{CONFIG["PLAID_LINK_PORT"]}/', new=1, autoraise=True)
    t.join()


if __name__ == '__main__':
    run_link_server()
