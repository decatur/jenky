# Run jenky server in background.
export JENKY_NAME=jenky
nohup venv/bin/python -m jenky --app_config=jenky_app_config.json --port=8094 >jenky.out 2>&1 &
echo $! > jenky.pid