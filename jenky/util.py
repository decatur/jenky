# Note: FastApi does not support asyncio subprocesses, so do not use it!
import logging
import os
from pathlib import Path
from typing import List
import subprocess

import psutil
from pydantic import BaseModel, Field

logger = logging.getLogger()

# git_cmd = 'C:/ws/tools/PortableGit/bin/git.exe'
# git_cmd = 'git'
git_cmd: str
base_url: Path


class Process(BaseModel):
    name: str
    cmd: List[str]
    env: dict
    running: bool
    create_time: float = Field(..., alias='createTime')


class Repo(BaseModel):
    repoName: str
    directory: str
    git_tag: str = Field(..., alias='gitTag')
    git_tags: List[str] = Field(..., alias='gitTags')
    git_branches: List[str] = Field(..., alias='gitBranches')
    git_message: str = Field(..., alias='gitMessage')
    processes: List[Process]


class Config(BaseModel):
    repos: List[Repo]
    git_cmd: str


def running_processes(repos: List[Repo]):
    for repo in repos:
        for proc in repo.processes:
            proc.running = False
            pid_file = base_url / repo.directory / (proc.name + '.pid')
            logger.debug(f'{pid_file}')
            if not pid_file.exists():
                logger.debug(f'Skipping {pid_file}')
                continue

            try:
                pid = int(pid_file.read_text())
            except Exception as e:
                logger.exception('Reading pid file')
                raise e

            try:
                p = psutil.Process(pid)
                proc.running = p.is_running()
            except psutil.NoSuchProcess:
                logger.debug(f'No such proccess {pid_file} {pid}')
                proc.running = False


def git_tag(git_dir: Path) -> str:
    logger.debug(git_dir)
    proc = subprocess.run(
        [git_cmd, 'describe', '--tags'],
        cwd=git_dir.as_posix(),
        capture_output=True)

    if proc.stderr:
        raise OSError(str(proc.stderr, encoding='ascii'))
    tag = str(proc.stdout, encoding='ascii')
    return tag


def fill_git_tag(repos: List[Repo]):
    for repo in repos:
        try:
            git_dir = base_url / repo.directory
            repo.git_tag = git_tag(git_dir)
        except OSError as e:
            repo.git_tag = None
            repo.git_message = str(e)


git_format = "%(refname:short) %(authorname) %(authordate:raw)"


def git_tags(git_dir: Path) -> List[str]:
    logger.debug(git_dir)
    proc = subprocess.run(
        [git_cmd, 'tag', '--sort', 'version:refname', f"--format={git_format}"],
        cwd=git_dir.as_posix(),
        capture_output=True)

    if proc.stderr:
        raise OSError(str(proc.stderr, encoding='utf8'))
    tags = [line.strip() for line in str(proc.stdout, encoding='utf8').splitlines()]
    return tags


def git_branches(git_dir: Path) -> List[str]:
    logger.debug(git_dir)
    proc = subprocess.run(
        [git_cmd, 'branch', '--sort=-committerdate', f"--format=%(HEAD) {git_format}"],
        cwd=git_dir.as_posix(),
        capture_output=True)

    if proc.stderr:
        raise OSError(str(proc.stderr, encoding='utf8'))
    branches = [line.strip() for line in str(proc.stdout, encoding='utf8').splitlines()]
    return branches


def fill_git_tags(repo: Repo):
    try:
        git_dir = base_url / repo.directory
        repo.git_tags = git_tags(git_dir)
    except OSError as e:
        repo.git_tags = []
        repo.git_message = str(e)


def fill_git_branches(repo: Repo):
    try:
        git_dir = base_url / repo.directory
        repo.git_branches = git_branches(git_dir)
    except OSError as e:
        repo.git_branches = []
        repo.git_message = str(e)


def git_pull(repo: Repo) -> str:
    """
    git pull
    """
    git_dir = base_url / repo.directory
    cmd = [git_cmd, 'pull']
    logger.debug(f'{git_dir} {cmd}')
    proc = subprocess.run(
        cmd,
        cwd=git_dir.as_posix(),
        capture_output=True)

    message = str(proc.stderr, encoding='ascii').rstrip()
    message += str(proc.stdout, encoding='ascii').rstrip()

    # if repo.git_tag != target_tag:
    #     proc = subprocess.run(
    #         [git_cmd, 'checkout', target_tag],
    #         cwd=git_dir.as_posix(),
    #         capture_output=True)
    #     message += '\n' + str(proc.stdout, encoding='ascii').rstrip()

    return message


def run(name: str, cwd: Path, cmd: List[str], env: dict):
    logger.debug(f'Running: {" ".join(cmd)}')
    my_env = os.environ
    my_env.update(env)
    kwargs = {}

    # subprocess.DETACHED_PROCESS: Open console window
    # subprocess.CREATE_NEW_PROCESS_GROUP  Only this will not detach
    # subprocess.CREATE_BREAKAWAY_FROM_JOB Only this will not detach
    # Both CREATE_NEW_PROCESS_GROUP and CREATE_BREAKAWAY_FROM_JOB will not detach
    # CREATE_NEW_CONSOLE
    # CREATE_NO_WINDOW(i.e.new

    # Does not work
    # creationflags = subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NO_WINDOW
    # creationflags = subprocess.CREATE_NEW_CONSOLE
    creationflags = subprocess.DETACHED_PROCESS  # Opens console window
    # creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW # Also opens console window
    # creationflags = subprocess.CREATE_BREAKAWAY_FROM_JOB
    #creationflags = subprocess.CREATE_NEW_CONSOLE #| subprocess.CREATE_NEW_PROCESS_GROUP #| subprocess.CREATE_NO_WINDOW
    kwargs['close_fds']: True
    if os.name == 'nt':
        pass
        #kwargs.update(creationflags=creationflags)
        #kwargs['close_fds']: True
    else:
        kwargs.update(start_new_session=True)

    pid = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=open((cwd / f'{name}.out').as_posix(), 'w').fileno(),
        stderr=subprocess.STDOUT,
        cwd=cwd.as_posix(),
        env=my_env,
        **kwargs).pid

    pid_file = base_url / cwd / (name + '.pid')
    pid_file.write_text(str(pid))


def kill(repos: List[Repo], repo_id: str, process_id: str):
    repo = repo_by_id(repos, repo_id)
    procs = [proc for proc in repo.processes if proc.name == process_id]
    if not procs:
        raise ValueError(repo_id)
    proc = procs[0]
    pid_file = base_url / repo.directory / (proc.name + '.pid')
    pid = int(pid_file.read_text())
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        logger.warning(f'No such process with pid {pid}')
        return

    proc.terminate()
    gone, alive = psutil.wait_procs([proc], timeout=3, callback=None)
    for p in alive:
        p.kill()


def repo_by_id(repos: List[Repo], repo_id: str) -> Repo:
    repos = [repo for repo in repos if repo.repoName == repo_id]
    if not repos:
        raise ValueError(repo_id)
    return repos[0]


def restart(repos: List[Repo], repo_id: str, process_id: str):
    repo = repo_by_id(repos, repo_id)
    procs = [proc for proc in repo.processes if proc.name == process_id]
    if not procs:
        raise ValueError(repo_id)
    proc = procs[0]
    run(proc.name, base_url / repo.directory, proc.cmd, proc.env)


# def find_root(procs: List[dict]):
#     parent = None
#     for proc in procs:
#         parents = [p for p in procs if p['pid'] == proc['ppid']]
#
#         if not parents:
#             assert parent is None
#             parent = proc
#         else:
#             assert len(parents) == 1
#
#     return parent

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
