import json
import logging
import sys
import time
from pathlib import Path
from typing import List

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
    if (util.base_url / repo.directory / '.git').is_dir():
        util.fill_git_tags(repo)
        util.fill_git_branches(repo)
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
    path = util.base_url / repo.directory / f'{process_id}.{std_x[3:]}'
    if path.exists():
        lines = get_tail(path)
        return Response(content=''.join(lines), media_type="text/plain")
    else:
        return Response(content='Not Found', media_type="text/plain", status_code=404)


class GitAction(BaseModel):
    action: str
    gitTag: str


@app.post("/repos/{repo_id}")
def post_repo(repo_id: str, action: GitAction):
    if action.action == 'pull':
        repo = util.repo_by_id(config.repos, repo_id)
        message = util.git_pull(repo)  # , target_tag=action.gitTag)
    else:
        assert False, 'Invalid action ' + action.action

    return dict(repo_id=repo_id, action=action.action, message=message)


config_file = 'config.json'
host = "127.0.0.1"
port = 8000
host = "127.0.0.1"

# TODO: Use argparse
for arg in sys.argv:
    if arg.startswith('--config='):
        config_file = arg.split('=')[1]
    elif arg.startswith('--port='):
        port = int(arg.split('=')[1])
    elif arg.startswith('--host='):
        host = arg.split('=')[1]

config_file = Path(config_file)
logger.info(f'Reading config from {config_file}')
config = Config.parse_obj(json.loads(config_file.read_text(encoding='utf8')))
util.git_cmd = config.git_cmd
util.base_url = config_file.parent.absolute()

uvicorn.run(app, host=host, port=port)
