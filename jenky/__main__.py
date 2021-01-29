import json
import sys
import time
from pathlib import Path
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.responses import RedirectResponse

from jenky import util

app = FastAPI()
app.mount("/static", StaticFiles(directory="jenky/html"), name="mymountname")


@app.get("/")
def get_root():
    return RedirectResponse(url='/static/index.html')


@app.get("/repos")
def get_repos():
    for repo in config:
        for process in repo['processes']:
            process['running'] = False

    def action(process, info, proc):
        process['running'] = proc.is_running()
        process['createTime'] = info['create_time']

    util.fill_process_running(config, action)
    util.fill_git_tag(config)
    util.fill_git_tags(config)
    return config


class Action(BaseModel):
    action: str


@app.post("/repos/{repo_id}/processes/{process_id}")
def post_process(repo_id: str, process_id: str, action: Action):
    if action.action == 'kill':
        util.kill(config, repo_id, process_id)
    elif action.action == 'restart':
        util.restart(config, repo_id, process_id)
        time.sleep(1)
    else:
        assert False, 'Invalid action ' + action.action

    return dict(repo_id=repo_id, process_id=process_id, action=action.action)


class GitAction(BaseModel):
    action: str
    gitTag: str

@app.post("/repos/{repo_id}")
def post_repo(repo_id: str, action: GitAction):
    if action.action == 'checkout':
        repo = util.repo_by_id(config, repo_id)
        message = util.git_pull(repo, target_tag=action.gitTag)
    else:
        assert False, 'Invalid action ' + action.action

    return dict(repo_id=repo_id, action=action.action, message=message)

config_file = 'config.json'
port = 8000

# TODO: Use argparse
for arg in sys.argv:
    if arg.startswith('--config='):
        config_file = arg.split('=')[1]
    elif arg.startswith('--port='):
        port = int(arg.split('=')[1])

config_file = Path(config_file)
print(f'Reading config from {config_file}')
config = json.loads(config_file.read_text(encoding='utf8'))


uvicorn.run(app, host="localhost", port=port)
