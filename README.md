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

# Docker

Jenky may be your alternative to
[Run multiple services in a container](https://docs.docker.com/config/containers/multi-service_container/)

In that case, use
````shell script
EXPOSE 5000
CMD ["python", "-m", "jenky",  "--app_config=jenky_app_config.json", "--port=5000", "--host=0.0.0.0"]
````

# Configure Jenky

A Jenky instance is customized via the `--app_config` command line option. You specify a JSON document with the fiels
* appName: The branding of the Jenky instance, as shown in the title of the UI.
* reposBase: Path to a folder. All sub-folders containing a `jenky_config.json` are considered repositories.
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
  * cmd: The command to run the process; Currently this must be a python command, see below.
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

## Python Runtime Resolution

If Jenky finds a virtual environment in the `venv` folder, then the python runtime is resolved according this
environment. 

# References
* [spotify/dh-virtualenv: Python virtualenvs in Debian packages](https://github.com/spotify/dh-virtualenv)
* [How We Deploy Python Code | Nylas](https://www.nylas.com/blog/packaging-deploying-python/)
* [Deployment - Full Stack Python](https://www.fullstackpython.com/deployment.html)
* [How to run systemd in a container](https://developers.redhat.com/blog/2019/04/24/how-to-run-systemd-in-a-container/)

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

## 0.2.0

* Deprecated git client support.

## 0.1.2
* PYTHONPATH is optional
* Fixed double unlick of pidfile
* Fixed css layout for reference select

## 0.1.1
* Check `requirements.txt` for changes after checkout/merge.
* Better git output formatting
* improved git interaction
* removed git refresh button

## 0.1.0
* added graphs to README.
* Do not use symlinkcopy of `python.exe`

## 0.0.9
* added process auto-run feature
