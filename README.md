# jenky
A deploy server for Python developers. 

When installed on a target server or Docker container, you can manage (checkout) repositories and monitor and restart 
processes using the Jenky UI.

## UI Example
![UI](jenky/html/ui.png)

## Jenky Object Model
![Jenky Object Model](jenky/html/jenky_object_model.png)

# Setup

````shell script
git clone https://github.com/decatur/jenky.git
cd jenky
python3.8 -m venv venv
. venv/Scripts/activate  # for MS Windows
pip install -r requirements.txt
````

# Start jenky server

Run Jenky from package.

````shell script
python -m jenky
# or with explicit default values
python -m jenky --app_config=jenky_app_config.json --host=127.0.0.1 --port=8000
````

or in a Dockerfile
````shell script
EXPOSE 5000
ENTRYPOINT ["tini", "-g", "--", "python", "-m jenky",  "--app_config=jenky_app_config.json", "--port=5000", "--host=0.0.0.0"]
````

If you plan to monitor and restart Jenky with Jenky (eat you own food), please use the `restart_jenky.sh` script.

# Configure Jenky

A Jenky instance is customized via the `--app_config` command line option. You specify a JSON document with the fiels
* appName: The branding of the Jenky instance, as shown in the title of the UI.
* reposBase: Path to a folder. All subfolders containing a `jenky_config.json` are considered repositories.
* gitCmd: The command to execute git on the target server.

Example `jenky_app_config.json` document:
````
{
  "appName": "Jenky 0.0.2, the gentle deploying app for Python",
  "reposBase": "../",
  "gitCmd": "C:/ws/tools/PortableGit/bin/git.exe"
}
````

# Configure Repository

Each repository and its list of processes needs to be configured with a `jenky_config.json` file in the root of
the repository:
* repoName: The unique name of the repository
* remoteUrl [optional]: A link to a representation of the repository
* processes: A list of processes
  * name: The unique (within this repo) name of the process
  * cmd: The command to run the process
  * env: Additional environment
  * running: Shall the process be auto-restarted when starting Jenky
  * createTime: Set this to 0

Example `jenky_config.json` file:
````
{
  "repoName": "jenky",
  "remoteUrl": "https://github.com/decatur/jenky",
  "processes": [
    {
      "name": "sample",
      "cmd": [
        "python",
        "scripts/sample.py"
      ],
      "env": {},
      "running": true,
      "createTime": 0
    }
  ]
}
````

# Start Processes from Shell

You can optionally/manually start processes which are managed by Jenky from shell. Jenky has a contract with processes
you have to respect. This contract is documented in `restart_jenky.sh`. Please adapt this script to your needs (Unix only).


# References
* [spotify/dh-virtualenv: Python virtualenvs in Debian packages](https://github.com/spotify/dh-virtualenv)
* [How We Deploy Python Code | Nylas](https://www.nylas.com/blog/packaging-deploying-python/)
* [Deployment - Full Stack Python](https://www.fullstackpython.com/deployment.html)


# Package and Publish

````shell script
vi setup.py
git commit . -m'bumped version'
git tag x.y.z
git push --tags; git push

python setup.py sdist
python -m twine upload dist/*
````

# Releases

# 0.1.1
* Check `requirements.txt` for changes after checkout/merge.
* Better git output formatting
* improved git interaction
* removed git refresh button

# 0.1.0
* added graphs to README.
* Do not use symlinkcopy of `python.exe`

# 0.0.9
* added process auto-run feature



