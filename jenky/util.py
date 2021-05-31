import argparse
import collections
import json
import logging
import os
import sys
from pathlib import Path
from pprint import pprint
from typing import List, Tuple, Optional, Dict, Callable
import subprocess

import persistqueue
import psutil
from pydantic import BaseModel, Field

logger = logging.getLogger(__package__)

cache_dir: Path
queue: Optional[persistqueue.Queue] = None
log_handler: Callable[[List[Dict]], None] = pprint


class Process(BaseModel):
    name: str
    cmd: List[str]
    env: dict
    keep_running: bool = Field(..., alias='keepRunning')
    create_time: Optional[float] = Field(alias='createTime')
    service_sub_domain: Optional[str] = Field(alias='serviceSubDomain')
    service_home_path: Optional[str] = Field(alias='serviceHomePath')
    log_url: Optional[str] = Field(alias='logUrl')
    # repo: Optional['Repo'] = None

    @property
    def repo(self) -> 'Repo':
        return repos_by_process_id[id(self)]

    # Note: pydantic does not support property setter, AFAIK
    # @repo.setter
    def set_repo(self, _repo: 'Repo'):
        repos_by_process_id[id(self)] = _repo


class Repo(BaseModel):
    repoName: str
    directory: Path
    git_tag: str = Field(default='', alias='gitRef')
    git_refs: Dict[str, str] = Field(default='', alias='gitRefs')
    # git_refs: List[dict] = Field(..., alias='gitRefs')
    # git_message: str = Field(..., alias='gitMessage')
    processes: List[Process]
    remote_url: Optional[str] = Field(alias='remoteUrl')

    def refresh(self):
        self.git_refs = git_ref(self.directory / '.git')
        self.git_tag = ','.join(self.git_refs.values())


repos_by_process_id: Dict[int, Repo] = {}


class Config(BaseModel):
    app_name: str = Field(..., alias='appName')
    version: str
    repos: List[Repo]


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


list_handler = ListHandler()


def find_process(pid_file: Path) -> Optional[psutil.Process]:
    logger.debug(f'Reading {pid_file}')

    if not pid_file.exists():
        logger.debug(f'No such file: {pid_file}')
        return None

    try:
        p_info = json.loads(pid_file.read_text())
    except Exception as e:
        logger.exception(f'Reading pid file {pid_file}')
        raise e

    pid = p_info['pid']
    assert isinstance(pid, int)

    try:
        p = psutil.Process(pid)
    except psutil.NoSuchProcess:
        logger.debug(f'No such proccess {pid}')
        return None

    is_running = p.is_running()
    if not is_running:
        return None
    elif is_running and p.status() == psutil.STATUS_ZOMBIE:
        # This happens whenever the process terminated but its creator did not because we do not wait.
        # p.terminate()
        p.wait()
        return None

    try:
        if abs(p.create_time() - p_info['create_time']) < 1:
            return p
        # pprint(p.environ())
        # if p.environ().get('JENKY_NAME', '') == proc.name:
        #    return p
    except psutil.AccessDenied:
        pass


def sync_process(proc: Process, directory: Path):
    pid_file = cache_dir / (proc.name + '.json')
    p = find_process(pid_file)

    if proc.keep_running and p:
        pass
    elif not proc.keep_running and not p:
        pass
    elif not proc.keep_running and p:
        logger.warning(f'Reaping process {proc.name}')
        p.terminate()
        # We need to wait unless a zombie stays in process list!
        # TODO: We should do this async.
        gone, alive = psutil.wait_procs([p], timeout=3, callback=None)
        for process in alive:
            process.kill()
        p = None
    elif proc.keep_running and not p:
        logger.warning(f'Restarting process {proc.name}')
        p = start_process(proc, directory)
        if p:
            pid_file.write_text(json.dumps(dict(pid=p.pid, create_time=p.create_time())))

    if p:
        proc.create_time = p.create_time()
    else:
        proc.create_time = None
        pid_file.unlink(missing_ok=True)


def sync_processes(repos: List[Repo]):
    for repo in repos:
        for proc in repo.processes:
            sync_process(proc, repo.directory)


def start_process(proc: Process, cwd: Path) -> Optional[psutil.Process]:
    name = proc.name
    proc_logger = logging.getLogger(name)
    current_working_directory = cwd.absolute().as_posix()
    proc_logger.info(f'Start process in {current_working_directory}')

    # TODO: On systemd, use it and replace jenky_config with service unit file.
    my_env = os.environ.copy()
    my_env.update(proc.env)

    proc.repo.refresh()
    my_env['JENKY_APP_VERSION'] = proc.repo.git_tag
    my_env['JENKY_LOG_FILE'] = queue.path.as_posix()
    # We want to have a clean PYTHONPATH. We only add to paths, . and site packages.
    # TODO: Is this a good idea?
    my_env['PYTHONPATH'] = '.;'

    if proc.cmd[0] == 'python':
        executable = 'python'
        pyvenv_file = Path('venv/pyvenv.cfg')
        if pyvenv_file.is_file():
            # We have a virtual environment.
            pyvenv = {k.strip(): v.strip() for k, v in (line.split('=') for line in open(pyvenv_file, 'r'))}
            # See https://docs.python.org/3/library/venv.html for MS-Windows vs Linux.
            if os.name == 'nt':
                # Do not use the exe from the venv because this is not a symbolic link and will generate 2 processes.
                # Note that we are guessing the location of the python installation. This will kind of works on
                # Windows, but not on linux.
                executable = pyvenv['home'] + '/python.exe'
                my_env['PYTHONPATH'] += 'venv/Lib/site-packages'
            elif os.name == 'posix':
                # Note that we cannot just use pyvenv['home'], because that will probably say /usr/bin, but not
                # what the python command was to create the venv!
                # This is a symlink, which is ok.
                # TODO: Shall we resolve the symlink?
                executable = 'venv/bin/python'
                my_env['PYTHONPATH'] += 'venv/lib/python3.8/site-packages'
            else:
                assert False, 'Unsupported os ' + os.name

        cmd = [executable] + proc.cmd[1:]
    else:
        cmd = proc.cmd

    proc_logger.debug(f'Running: {" ".join(cmd)}')
    proc_logger.debug(f'PYTHONPATH: {my_env.get("PYTHONPATH", "")}')

    out_file = cache_dir / f'{name}.out'
    out_file.unlink(missing_ok=True)
    stdout = open(out_file.as_posix(), 'w')

    if os.name == 'nt':
        kwargs = {}
    else:
        # This prevents that killing this process will kill the child process.
        kwargs = dict(start_new_session=True)

    # Note: FastApi does not support asyncio subprocesses, so do not use it!
    popen = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,  # TODO: We do not actually need this, even if subprocess reads from stdin.
        stdout=stdout,
        stderr=subprocess.STDOUT,
        cwd=current_working_directory,
        env=my_env,
        **kwargs)

    try:
        p = psutil.Process(popen.pid)
    except psutil.NoSuchProcess:
        proc_logger.warning(f'No such proccess {popen.pid}')
        return

    is_running = p.is_running()
    if not is_running:
        return
    elif is_running and p.status() == psutil.STATUS_ZOMBIE:
        # This happens whenever the process terminated but its creator did not because we do not wait.
        # p.terminate()
        p.wait()
        return

    return p


def get_by_id(repos: List[Repo], repo_id: str, process_id: str) -> Tuple[Repo, Process]:
    repo = repo_by_id(repos, repo_id)
    procs = [proc for proc in repo.processes if proc.name == process_id]
    if not procs:
        raise ValueError(repo_id)
    return repo, procs[0]


def repo_by_id(repos: List[Repo], repo_id: str) -> Repo:
    repos = [repo for repo in repos if repo.repoName == repo_id]
    if not repos:
        raise ValueError(repo_id)
    return repos[0]


def get_tail(path: Path) -> List[str]:
    logger.debug(path)
    with open(path.as_posix(), "rb") as f:
        try:
            f.seek(-50*1024, os.SEEK_END)
            byte_lines = f.readlines()
            if len(byte_lines):
                byte_lines = byte_lines[1:]
            else:
                # So we are in the middle of a line and could hit a composed unicode character.
                # But we just ignore that...
                pass
        except:
            # file size too short
            f.seek(0)
            byte_lines = f.readlines()
    lines = [str(byte_line, encoding='utf8') for byte_line in byte_lines]
    return lines


def is_file(p: Path) -> bool:
    try:
        return p.is_file()
    except PermissionError:
        return False


def collect_repos(repo_infos: List[dict]) -> List[Repo]:
    repos: List[Repo] = []

    for repo_info in repo_infos:
        repo_dir = repo_info['directory']
        logger.info(f'Collect repo {repo_dir}')
        repo = Repo.parse_obj(repo_info)
        repo.refresh()
        repos.append(repo)
        for proc in repo.processes:
            # repos_by_process_id[id(proc)] = repo
            proc.set_repo(repo)
    return repos


def git_named_refs(git_hash: str, git_dir: Path) -> Dict[str, str]:
    """
    Returns all named tag or reference for the provided hash and the hash.
    This method does not need nor uses a git client installation.
    """

    refs = dict(hash=git_hash)
    ref_dir = git_dir / 'refs'
    for item in ref_dir.glob('**/*'):
        if item.is_file() and git_hash == item.read_text(encoding='ascii').strip():
            refs[item.parent.relative_to(ref_dir).as_posix()] = item.name

    return refs


def git_ref(git_dir: Path) -> Dict[str, str]:
    """
    Finds the git reference (tag or branch) of this working directory.
    This method does not need nor uses a git client installation.
    """

    logger.debug(f'Scanning {git_dir.absolute()}')
    head = (git_dir / 'HEAD').read_text(encoding='ascii').strip()
    if head.startswith('ref:'):
        # This is a branch, example "ref: refs/heads/master"
        ref_path = head.split()[1]
        git_hash = (git_dir / ref_path).read_text(encoding='ascii').strip()
    else:
        # This is detached, and head is a hash AFAIK
        git_hash = head

    return git_named_refs(git_hash, git_dir)


def read_logs():
    items = []
    while True:  # not queue.empty(), see https://github.com/peter-wangxu/persist-queue/issues/76#issuecomment-850350655
        try:
            item = queue.get(block=False)
        except persistqueue.exceptions.Empty:
            break
        items.append(item)

    if items:
        log_handler(items)
        queue.task_done()


def parse_args() -> Tuple[str, int, Config]:
    global cache_dir, queue

    parser = argparse.ArgumentParser()
    parser.add_argument('--host', type=str, help='Server host', default="127.0.0.1")
    parser.add_argument('--port', type=int, help='Server port', default=8000)
    parser.add_argument('--app-config', type=str,
                        help='Path to JSON app configuration. This argument is env-var interpolated.',
                        default="jenky_app_config.json")
    parser.add_argument('--log-level', type=str, help='Log level', default="INFO")
    parser.add_argument('--cache-dir', type=str, help='Path to cache dir', default=".jenky_cache")
    args = parser.parse_args()

    app_config_path = Path(args.app_config.format(**os.environ))
    cache_dir = Path(args.cache_dir)
    assert cache_dir.is_dir()
    app_config = json.loads(app_config_path.read_text(encoding='utf8'))
    for repo in app_config['repos']:
        repo['directory'] = (app_config_path.parent / repo['directory']).resolve()

    jenky_version = ','.join(git_ref(Path('./.git')).values()) if Path('./.git').is_dir() else ''
    config = Config(appName=app_config['appName'], version=jenky_version, repos=collect_repos(app_config['repos']))

    logger.setLevel(logging.__dict__[args.log_level])
    logger.info(args)

    queue = persistqueue.SQLiteQueue((cache_dir / 'mypath').absolute())

    stream_handler = logging.StreamHandler(sys.stdout)

    for handler in (stream_handler, list_handler):
        handler.formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(funcName)s - %(message)s')
        logger.addHandler(handler)

    logger.info(f'Cache path is {queue.path}')

    return args.host, args.port, config
