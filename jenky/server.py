
import asyncio
import base64
import json
import logging.handlers

import time
from pathlib import Path
from typing import List, Callable, Tuple

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.responses import RedirectResponse, Response, JSONResponse

from jenky import util
from jenky.util import Config, get_tail


logger = logging.getLogger(__package__)
app = FastAPI()


async def schedule(action: Callable[[], float], start_at: float):
    while True:
        await asyncio.sleep(start_at - time.time())
        try:
            # assert False, 'FooBar'
            start_at = action()
        except Exception as e:
            logger.exception(str(action))
            start_at += 1
        if start_at < 0.:
            break


@app.on_event("startup")
async def startup_event():
    def sync_processes_action() -> float:
        util.sync_processes(app.state.config.repos)
        return time.time() + 5

    def read_logs_action() -> float:
        util.read_logs()
        return time.time() + 1

    asyncio.create_task(schedule(sync_processes_action, time.time() + 5))
    asyncio.create_task(schedule(read_logs_action, time.time() + 1))


html_root = Path(__file__).parent / 'html'
app.mount("/static", StaticFiles(directory=html_root.as_posix()), name="mymountname")


@app.get("/")
def home():
    return RedirectResponse(url='/static/index.html')


@app.get("/mirror")
def home(request: Request) -> dict:
    oidc_data = request.headers.get("x-amzn-oidc-data", "")
    if oidc_data:
        # See https://docs.aws.amazon.com/elasticloadbalancing/latest/application/listener-authenticate-users.html
        payload_json = base64.b64decode(oidc_data.split('.')[1]).decode("utf-8")
        payload = json.loads(payload_json)
    return JSONResponse(content=dict(headers=request.headers.items(), userName=payload['name']))


@app.get("/repos")
def get_repos() -> Config:
    # refresh repos
    # config.repos = util.collect_repos(app_config['repos'])
    # util.sync_processes(config.repos)
    for repo in app.state.config.repos:
        repo.refresh()
    return app.state.config


class Action(BaseModel):
    action: str


@app.post("/repos/{repo_id}/processes/{process_id}")
def change_process_state(repo_id: str, process_id: str, action: Action):
    assert action.action in {'kill', 'restart'}
    _, proc = util.get_by_id(app.state.config.repos, repo_id, process_id)
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
    for item in util.list_handler.buffer:
        if item[0] == last_event_id:
            break
        logs_since.append(item)

    return dict(logsSince=logs_since, maxLength=util.list_handler.buffer.maxlen, repos=app.state.config.repos)




