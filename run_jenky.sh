# Run jenky server in background.
nohup venv/bin/python -m jenky --app_config=jenky_app_config.json --port=8094 cmd >jenky.out 2>&1 &
echo $! > jenky.pid