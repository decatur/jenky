# Note: FastApi does not support asyncio subprocesses, so do not use it!
import glob
import json
import logging
import os
from pathlib import Path
from typing import List, Tuple, Optional, Set
import subprocess

import psutil
from pydantic import BaseModel, Field

logger = logging.getLogger()

# git_cmd = 'C:/ws/tools/PortableGit/bin/git.exe'
# git_cmd = 'git'
git_cmd: str = ''
git_version: str = ''
cache_dir: Path


class Process(BaseModel):
    name: str
    cmd: List[str]
    env: dict
    keep_running: bool = Field(..., alias='keepRunning')
    create_time: Optional[float] = Field(alias='createTime')
    service_sub_domain: Optional[str] = Field(alias='serviceSubDomain')
    service_home_path: Optional[str] = Field(alias='serviceHomePath')


class Repo(BaseModel):
    repoName: str
    directory: Path
    git_tag: str = Field(..., alias='gitRef')
    # git_refs: List[dict] = Field(..., alias='gitRefs')
    # git_message: str = Field(..., alias='gitMessage')
    processes: List[Process]
    remote_url: Optional[str] = Field(alias='remoteUrl')


class Config(BaseModel):
    app_name: str = Field(..., alias='appName')
    repos: List[Repo]


def find_process_by_name(name: str, pid_file: Path) -> Optional[psutil.Process]:
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
    p = find_process_by_name(proc.name, pid_file)

    if proc.keep_running and p:
        pass
    elif not proc.keep_running and not p:
        pass
    elif not proc.keep_running and p:
        logger.warning(f'Reaping process {proc.name}')
        p.terminate()
        # We need to wait unless a zombie stays in process list!
        gone, alive = psutil.wait_procs([p], timeout=3, callback=None)
        for process in alive:
            process.kill()
        p = None
    elif proc.keep_running and not p:
        logger.warning(f'Restarting process {proc.name}')
        p = start_process(proc.name, cache_dir, proc.cmd, proc.env)
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


def start_process(name: str, cwd: Path, cmd: List[str], env: dict) -> Optional[psutil.Process]:
    # TODO: On systemd, use it and replace jenky_config with service unit file.
    my_env = os.environ.copy()
    my_env.update(env)
    # TODO: Use tuple (PID, START_TIME) to id a process.
    # my_env['JENKY_NAME'] = name

    if cmd[0] == 'python':
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
                my_env['PYTHONPATH'] = 'venv/Lib/site-packages'
            elif os.name == 'posix':
                # Note that we cannot just use pyvenv['home'], because that will probably say /usr/bin, but not
                # what the python command was to create the venv!
                # This is a symlink, which is ok.
                # TODO: Shall we resolve the symlink?
                executable = 'venv/bin/python'
                my_env['PYTHONPATH'] = 'venv/lib/python3.8/site-packages'
            else:
                assert False, 'Unsupported os ' + os.name

        cmd = [executable] + cmd[1:]

    logger.debug(f'Running: {" ".join(cmd)}')
    logger.info(f'PYTHONPATH: {my_env.get("PYTHONPATH", "")}')

    out_file = cwd / f'{name}.out'
    out_file.unlink(missing_ok=True)
    stdout = open(out_file.as_posix(), 'w')

    if os.name == 'nt':
        kwargs = {}
    else:
        # This prevents that killing this process will kill the child process.
        kwargs = dict(start_new_session=True)

    popen = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,  # TODO: We do not actually need this, even if subprocess reads from stdin.
        stdout=stdout,
        stderr=subprocess.STDOUT,
        cwd=cwd.absolute().as_posix(),
        env=my_env,
        **kwargs)


    try:
        p = psutil.Process(popen.pid)
    except psutil.NoSuchProcess:
        logger.warning(f'No such proccess {popen.pid}')
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
        #if 'directory' in repo_info:
        #    repo_info['directory'] = (repo_dir / config['directory']).resolve()
        #else:
        #repo_info['directory'] = repo_dir

        if (repo_dir / '.git').is_dir():
            repo_info["gitRef"] = str(git_ref(repo_dir / '.git'))

        if not repo_info.get("gitRef", ""):
            repo_info["gitRef"] = 'No git ref found'

        repos.append(Repo.parse_obj(repo_info))
    return repos


def git_named_refs(git_hash: str, git_dir: Path) -> Set[str]:
    """
    Returns all named tag or reference for the provided hash and the hash.
    This method does not need nor uses a git client installation.
    """

    refs = set([git_hash])
    for item_name in glob.iglob(git_dir.as_posix() + '/refs/**', recursive=True):
        file = Path(item_name)
        if file.is_file() and git_hash == file.read_text(encoding='ascii').strip():
            refs.add(file.name)

    return refs


def git_ref(git_dir: Path) -> Set[str]:
    """
    Finds the git reference (tag or branch) of this working directory.
    This method does not need nor uses a git client installation.
    """

    head = (git_dir / 'HEAD').read_text(encoding='ascii').strip()
    if head.startswith('ref:'):
        # This is a branch, example "ref: refs/heads/master"
        ref_path = head.split()[1]
        git_hash = (git_dir / ref_path).read_text(encoding='ascii').strip()
    else:
        # This is detached, and head is a hash AFAIK
        git_hash = head

    return git_named_refs(git_hash, git_dir)
