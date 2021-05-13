import argparse
import asyncio
import collections
import json
import logging
import logging.handlers
import sys
import time
from pathlib import Path
from queue import SimpleQueue
from typing import List, Callable

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


class ListHandler(logging.StreamHandler):
    def __init__(self):
        super().__init__()
        self.buffer = collections.deque(maxlen=200)

    def emit(self, record):
        msg = self.format(record)
        self.buffer.append([record.created, msg])


handler = ListHandler()
handler.formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s %(funcName)s - %(message)s')
logger.addHandler(handler)

app = FastAPI()


async def schedule(action: Callable[[], float], start_at: float):
    while True:
        await asyncio.sleep(start_at - time.time())
        start_at = action()
        if start_at < 0.:
            break


def sync_processes_action() -> float:
    # util.sync_processes(config.repos)
    return time.time() + 5


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(schedule(sync_processes_action, time.time() + 5))


html_root = Path(__file__).parent / 'html'
app.mount("/static", StaticFiles(directory=html_root), name="mymountname")


@app.get("/")
def home():
    return RedirectResponse(url='/static/index.html')


@app.get("/repos")
def get_repos() -> Config:
    # refresh repos
    # config.repos = util.collect_repos(app_config['repos'])
    # util.sync_processes(config.repos)
    return config


class Action(BaseModel):
    action: str


@app.post("/repos/{repo_id}/processes/{process_id}")
def change_process_state(repo_id: str, process_id: str, action: Action):
    assert action.action in {'kill', 'restart'}
    repo, proc = util.get_by_id(config.repos, repo_id, process_id)
    proc.keep_running = (action.action == 'restart')
    util.sync_process(proc, repo.directory)
    time.sleep(1)

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


@app.get("/logs")
def get_logs(created: float) -> Response:
    diff = []
    for item in reversed(handler.buffer):
        diff.append(item)
        if item[0] == created:
            break
    return diff


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


uvicorn.run(app, host=args.host, port=args.port)
