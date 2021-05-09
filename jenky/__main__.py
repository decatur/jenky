import argparse
import json
import logging
import sys
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.responses import RedirectResponse, Response

from jenky import util
from jenky.util import Config, get_tail

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s %(funcName)s - %(message)s')
logger.addHandler(handler)

app = FastAPI()
html_root = Path(__file__).parent / 'html'
app.mount("/static", StaticFiles(directory=html_root), name="mymountname")


@app.get("/")
def home():
    return RedirectResponse(url='/static/index.html')


@app.get("/repos")
def get_repos() -> Config:
    # refresh repos
    config.repos = util.collect_repos(app_config['repos'])
    util.running_processes(config.repos)
    return config


class Action(BaseModel):
    action: str


@app.post("/repos/{repo_id}/processes/{process_id}")
def change_process_state(repo_id: str, process_id: str, action: Action):
    if action.action == 'kill':
        killed = util.kill(config.repos, repo_id, process_id)
        if not killed:
            return Response(content='Process was not running', media_type="text/plain", status_code=404)
    elif action.action == 'restart':
        util.restart(config.repos, repo_id, process_id)
        time.sleep(1)
    else:
        assert False, 'Invalid action ' + action.action

    return dict(repo_id=repo_id, process_id=process_id, action=action.action)


@app.get("/repos/{repo_id}/processes/{process_id}/{log_type}")
def get_process_log(repo_id: str, process_id: str, log_type: str) -> Response:
    repo = util.repo_by_id(config.repos, repo_id)
    path = repo.directory / f'{process_id}.{log_type}'
    if path.exists():
        lines = get_tail(path)
        return Response(content=''.join(lines), media_type="text/plain")
    else:
        return Response(content='Not Found', media_type="text/plain", status_code=404)


parser = argparse.ArgumentParser()
parser.add_argument('--host', type=str, help='host', default="127.0.0.1")
parser.add_argument('--port', type=int, help='port', default=8000)
parser.add_argument('--app_config', type=str, help='jenky_app_config', default="jenky_app_config.json")
args = parser.parse_args()

app_config_path = Path(args.app_config)
logger.info(f'Reading config from {app_config_path}')
app_config = json.loads(app_config_path.read_text(encoding='utf8'))
for repo in app_config['repos']:
    repo['path'] = (app_config_path.parent / repo['path']).resolve()

# repo_dirs = [(app_config_path.parent / repo).resolve() for repo in app_config['repos']]
config = Config(appName=app_config['appName'], repos=util.collect_repos(app_config['repos']))
util.auto_run_processes(config.repos)

uvicorn.run(app, host=args.host, port=args.port)
