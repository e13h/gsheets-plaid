import os
import shlex
import shutil
import subprocess
import webbrowser
from time import sleep

from dotenv import dotenv_values

CONFIG = dotenv_values('.env')


def main():
    """Run Plaid Link flow.
    """
    # Start tiny-quickstart
    command = f'{shutil.which("npm")} start'
    print(shlex.split(command))
    plaid_env = os.environ.copy()
    plaid_env.update(CONFIG)
    p = subprocess.Popen(shlex.split(command), cwd='./tiny-quickstart', env=plaid_env)

    sleep(1)
    # Direct the user to Plaid Link
    webbrowser.open("http://localhost:8080/", new=1, autoraise=True)
    p.wait()


if __name__ == '__main__':
    main()
