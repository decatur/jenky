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

````bash
venv/Scripts/python -m jenky -h
usage: __main__.py [-h] [--host HOST] [--port PORT] [--app-config APP_CONFIG]
                   [--log-level LOG_LEVEL] [--cache-dir CACHE_DIR]

optional arguments:
  -h, --help            show this help message and exit
  --host HOST           Server host
  --port PORT           Server port
  --app-config APP_CONFIG
                        Path to JSON app configuration. This argument is env-
                        var interpolated.
  --log-level LOG_LEVEL
                        Log level
  --cache-dir CACHE_DIR
                        Path to cache dir
````

````shell script
python -m jenky
# or with explicit default values
python -m jenky --app-config=jenky_app_config.json --host=127.0.0.1 --port=8000 --log-level=DEBUG --cache-dir=./jenky
````

# Docker

Jenky may be your alternative to
[Run multiple services in a container](https://docs.docker.com/config/containers/multi-service_container/)

In that case, use
````shell script
EXPOSE 5000
CMD ["python", "-m", "jenky",  "--app_config={stage}/jenky_app_config.json", "--port=5000", "--host=0.0.0.0"]
````

# Configure Jenky

A Jenky instance is customized via the `--app-config` command line option, see [sample config](sample/jenky_app_config.json).

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

## 0.2.4

* Keep processes running

## 0.2.3

* Repo Config can now be embedded in App Config

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
