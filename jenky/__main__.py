import argparse
import asyncio
import collections
import json
import logging.handlers
import os
import sys
import time
from pathlib import Path
from typing import List, Callable, Tuple

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.responses import RedirectResponse, Response

from jenky import util
from jenky.util import Config, get_tail, git_ref


class ListHandler(logging.StreamHandler):
    def __init__(self):
        super().__init__()
        self.buffer = collections.deque(maxlen=1000)
        self._current_time = 0
        self._current_index = 0

    def unique_id(self, timestamp: float) -> str:
        if int(timestamp) == self._current_time:
            self._current_index += self._current_index
        else:
            self._current_index = 0
            self._current_time = int(timestamp)
        return str(f'{self._current_time}i{self._current_index}')

    def emit(self, record):
        msg = self.format(record)
        self.buffer.appendleft((self.unique_id(record.created), msg))


logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
stream_handler = logging.StreamHandler(sys.stdout)
list_handler = ListHandler()

for handler in (stream_handler, list_handler):
    handler.formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(funcName)s - %(message)s')
    logger.addHandler(handler)

app = FastAPI()


async def schedule(action: Callable[[], float], start_at: float):
    while True:
        await asyncio.sleep(start_at - time.time())
        start_at = action()
        if start_at < 0.:
            break


def sync_processes_action() -> float:
    util.sync_processes(config.repos)
    return time.time() + 5


@app.on_event("startup")
async def startup_event():
    # loop = asyncio.get_running_loop()
    # for sig in (signal.SIGTERM, signal.SIGINT):  # signal.SIGHUP,
    #     loop.add_signal_handler(
    #         sig, lambda s: print(s))
    asyncio.create_task(schedule(sync_processes_action, time.time() + 5))


html_root = Path(__file__).parent / 'html'
app.mount("/static", StaticFiles(directory=html_root.as_posix()), name="mymountname")


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
    _, proc = util.get_by_id(config.repos, repo_id, process_id)
    proc.keep_running = (action.action == 'restart')
    # util.sync_process(proc, repo.directory)
    time.sleep(1)

    return dict(repo_id=repo_id, process_id=process_id, action=action.action)


@app.get("/repos/{repo_id}/processes/{process_id}/{log_type}")
def get_process_log(repo_id: str, process_id: str, log_type: str) -> Response:
    # repo = util.repo_by_id(config.repos, repo_id)
    path = util.cache_dir / f'{process_id}.{log_type}'
    if path.exists():
        lines = get_tail(path)
        return Response(content=''.join(lines), media_type="text/plain")
    else:
        return Response(content='Not Found', media_type="text/plain", status_code=404)


@app.get("/logs")
def get_logs(last_event_id: str = None) -> dict:
    logs_since: List[Tuple[str, str]] = []
    for item in list_handler.buffer:
        if item[0] == last_event_id:
            break
        logs_since.append(item)

    return dict(logsSince=logs_since, maxLength=list_handler.buffer.maxlen, repos=config.repos)


parser = argparse.ArgumentParser()
parser.add_argument('--host', type=str, help='Server host', default="127.0.0.1")
parser.add_argument('--port', type=int, help='Server port', default=8000)
parser.add_argument('--app-config', type=str,
                    help='Path to JSON app configuration. This argument is env-var interpolated.',
                    default="jenky_app_config.json")
parser.add_argument('--log-level', type=str, help='Log level', default="INFO")
parser.add_argument('--cache-dir', type=str, help='Path to cache dir', default=".jenky_cache")
args = parser.parse_args()

logger.info(args)

logger.setLevel(logging.__dict__[args.log_level])

app_config_path = Path(args.app_config.format(**os.environ))
util.cache_dir = Path(args.cache_dir)
assert util.cache_dir.is_dir()
app_config = json.loads(app_config_path.read_text(encoding='utf8'))
for repo in app_config['repos']:
    repo['directory'] = (app_config_path.parent / repo['directory']).resolve()

jenky_version = ','.join(git_ref(Path('./.git'))) if Path('./.git').is_dir() else ''
config = Config(appName=app_config['appName'], version=jenky_version, repos=util.collect_repos(app_config['repos']))

uvicorn.run(app, host=args.host, port=args.port)
