#!/bin/bash
#
# Runs jenky server in background.
# This is a template for the contract jenky needs for running processes:
# 1) A process is identified by both
# 1.1) A pid-file containing the PID of the process, and
# 1.2) The env var JENKY_NAME.
# 2.) Both stdout and stderr are directed to the file of said name
#
# 1.1 is for performance reasons but cannot be used to identify the process as PIDs are reused.
# 1.2 is used to verify that the process to which the pid-file points to is genuine.
#
# Usage: run_jenky my_jenky_app_config

if [[ -f jenky.pid && -d /proc/$(cat jenky.pid) ]]
then
  if strings /proc/$(cat jenky.pid)/environ | egrep JENKY_NAME=jenky
  then
    kill $(cat jenky.pid)
  fi
fi

cd jenky_dir
export JENKY_NAME=jenky
nohup venv/bin/python -m jenky --app_config=$1 --port=8094 >$JENKY_NAME.out 2>&1 &
echo $! > $JENKY_NAME.pid