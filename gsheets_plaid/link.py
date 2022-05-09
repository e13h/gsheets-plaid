import threading
import webbrowser
from time import sleep

from gsheets_plaid.initialization import CONFIG
from gsheets_plaid.resources.plaid_link_server.server import app


def run_link_server(port: int = None, env: str = None, redirect_uri: str = None):
    """Run Plaid Link flow.
    """
    if port:
        CONFIG['PLAID_LINK_PORT'] = port
    if env:
        CONFIG['PLAID_ENV'] = env
    if redirect_uri:
        CONFIG['PLAID_SANDBOX_REDIRECT_URI'] = redirect_uri
    t = threading.Thread(target=app.run, kwargs={'host': 'localhost', 'port': CONFIG['PLAID_LINK_PORT']})
    # working_dir = str(files('gsheets_plaid.resources.plaid_link_server'))
    # p = subprocess.Popen(shlex.split(command), cwd=working_dir)
    t.start()
    sleep(1)  # Wait for the server to start

    # Direct the user to Plaid Link
    webbrowser.open(f'http://localhost:{CONFIG["PLAID_LINK_PORT"]}/', new=1, autoraise=True)
    t.join()


if __name__ == '__main__':
    run_link_server()
