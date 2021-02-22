# jenky
A build and deploy server for Python developers

# 🚧 This is an alpha release!

# Setup

````shell script
git clone https://github.com/decatur/jenky.git
cd jenky
python3.8 -m venv venv
. venv/Scripts/activate
pip install -r requirements.txt
````

# Start jenky server

Shown in example are default config file and default port.

````shell script
python -m jenky --config=config.json --port=8000
````

````
. venv/bin/activate
python -m jenky --config=../jenky_config.json --port=8094
````

# Usage

* Start the ...
* Kill ...
* Checkout ...

# Start Processes from Shell

## Unix

From bash
````shell script
venv/Scripts/python.exe foo.py & cat $! > run_test.pid
````

## MS Windows

From git bash
````shell script
venv/Scripts/python.exe foo.py & cat /proc/$!/winpid > run_test.pid
````

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

python3 setup.py sdist
python3 -m twine upload dist/*
````