import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.responses import RedirectResponse, Response

from jenky import util
from jenky.util import Config, Repo, get_tail

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
    util.running_processes(config.repos)
    return config


@app.get("/repos/{repo_id}")
def get_repo(repo_id: str) -> Repo:
    repo = util.repo_by_id(config.repos, repo_id)
    # util.fill_git_tag(config.repos)
    if (repo.directory / '.git').is_dir():
        util.fill_git_refs(repo)
    else:
        repo.git_message = 'Not a git repository'
    return repo


class Action(BaseModel):
    action: str


@app.post("/repos/{repo_id}/processes/{process_id}")
def post_process(repo_id: str, process_id: str, action: Action):
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


@app.get("/repos/{repo_id}/processes/{process_id}/{std_x}")
def get_process_log(repo_id: str, process_id: str, std_x: str) -> Response:
    repo = util.repo_by_id(config.repos, repo_id)
    path = repo.directory / f'{process_id}.{std_x[3:]}'
    if path.exists():
        lines = get_tail(path)
        return Response(content=''.join(lines), media_type="text/plain")
    else:
        return Response(content='Not Found', media_type="text/plain", status_code=404)


class GitAction(BaseModel):
    action: str
    gitRef: Optional[str]


@app.post("/repos/{repo_id}")
def post_repo(repo_id: str, action: GitAction):
    repo = util.repo_by_id(config.repos, repo_id)
    if action.action == 'checkout':
        message = util.git_checkout(repo, git_ref=action.gitRef)
    elif action.action == 'fetch':
        message = util.git_fetch(repo)
        # TODO: Not so nice to pass id here
        get_repo(repo_id)
        repo.git_message = message
        return repo
    else:
        assert False, 'Invalid action ' + action.action

    return dict(repo_id=repo_id, action=action.action, message=message)


parser = argparse.ArgumentParser()
parser.add_argument('--host', type=str, help='host', default="127.0.0.1")
parser.add_argument('--port', type=int, help='port', default=8000)
parser.add_argument('--app_config', type=str, help='jenky_app_config', default="jenky_app_config.json")
args = parser.parse_args()

app_config = Path(args.app_config)
logger.info(f'Reading config from {app_config}')
data = json.loads(app_config.read_text(encoding='utf8'))
repos_base = (Path(__file__).parent.parent / data['reposBase']).resolve()
config = Config(appName=data['appName'], gitCmd=data['gitCmd'], repos=util.collect_repos(repos_base))
util.git_cmd = config.git_cmd

uvicorn.run(app, host=args.host, port=args.port)
