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
            if not pid_file.is_file():
                continue

            pid = int(pid_file.read_text())
            try:
                p = psutil.Process(pid)
                proc.running = p.is_running()
            except psutil.NoSuchProcess:
                logger.exception(f'Cannot read {pid_file}')
                proc.running = False

# def running_processes_(repos: List[Repo]) -> Dict[Tuple[str, str], ProcessInfo]:
#     procs_by_name = {}
#     for proc in psutil.process_iter(attrs=None, ad_value=None):
#         d = proc.as_dict(attrs=['pid', 'ppid', 'name', 'cwd', 'exe', 'username', 'cmdline', 'create_time', 'environ'],
#                          ad_value=None)
#         if 'username' in d and d.get('cwd', None):
#             for repo in repos:
#                 repo_dir = base_url / repo.directory
#
#                 for process in repo.processes:
#                     name = process.name
#                     if Path(d['cwd']).samefile(repo_dir) and match_cmd(process.cmd, d['cmdline']):
#                         assert name not in procs_by_name
#                         info = ProcessInfo()
#                         info.create_time = d['create_time']
#                         info.popen = Process
#                         procs_by_name[name] = info
#
#     return procs_by_name


# def fill_process_running(repos: List[Repo], action):
#     procs_by_name = {}
#     for proc in psutil.process_iter(attrs=None, ad_value=None):
#         d = proc.as_dict(attrs=['pid', 'ppid', 'name', 'cwd', 'exe', 'username', 'cmdline', 'create_time', 'environ'],
#                          ad_value=None)
#         if 'username' in d and d.get('cwd', None):
#             # print(f'{proc.name()} {proc.pid} {proc.ppid()} {cmd}')
#             # pprint(d)
#             # print(proc.cmdline())
#             # line = proc.cmdline()
#             for repo in repos:
#                 repo_dir = base_url / repo.directory
#
#                 for process in repo.processes:
#                     # cmd_pattern = process['cmdPattern']
#                     # index = cmd_pattern['index']
#                     # if len(line) > index and cmd_pattern['pattern'] in line[index]:
#                     name = process.name
#                     # print(Path(d['cwd']))
#                     # print(p)
#                     if Path(d['cwd']).samefile(repo_dir) and match_cmd(process.cmd, d['cmdline']):
#                         if name not in procs_by_name:
#                             procs_by_name[name] = dict(process=process, procs=[])
#                         d['proc'] = proc
#                         procs_by_name[name]['procs'].append(d)
#
#     print('############### procs_by_name')
#     pprint(procs_by_name.keys())
#
#     for name, info in procs_by_name.items():
#         root = find_root(info['procs'])
#         action(info['process'], root, root['proc'])


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
    logger.debug(cmd)
    my_env = os.environ
    my_env.update(env)
    kwargs = {}
    kwargs.update(start_new_session=True)
    pid = subprocess.Popen(
        cmd,
        stdout=open((cwd / f'{name}.out').as_posix(), 'w'),
        stderr=open((cwd / f'{name}.err').as_posix(), 'w'),
        # stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
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
    proc = psutil.Process(pid)
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


def find_root(procs: List[dict]):
    parent = None
    for proc in procs:
        parents = [p for p in procs if p['pid'] == proc['ppid']]

        if not parents:
            assert parent is None
            parent = proc
        else:
            assert len(parents) == 1

    return parent
