import threading
import webbrowser
from time import sleep

from gsheets_plaid.resources.plaid_link_server.server import app


def run_link_server(port: int):
    """Run Plaid Link flow.
    """
    t = threading.Thread(target=app.run, kwargs={'host': 'localhost', 'port': port})
    t.start()
    sleep(1)  # Wait for the server to start

    # Direct the user to Plaid Link
    webbrowser.open(f'http://localhost:{port}/', new=1, autoraise=True)
    t.join()


if __name__ == '__main__':
    run_link_server()
