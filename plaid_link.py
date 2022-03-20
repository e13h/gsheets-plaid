from time import sleep
import webbrowser
import subprocess
import shutil
import shlex


def main():
    """Run Plaid Link flow.
    """
    # Start tiny-quickstart
    command = f'{shutil.which("npm")} start'
    print(shlex.split(command))
    p = subprocess.Popen(shlex.split(command), cwd='./tiny-quickstart')

    sleep(1)
    # Direct the user to Plaid Link
    webbrowser.open("http://localhost:8080/", new=1, autoraise=True)
    p.wait()


if __name__ == '__main__':
    main()
