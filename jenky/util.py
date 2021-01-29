# Note: FastApi does not support asyncio subprocesses, so do not use it!
import logging
from pathlib import Path
from pprint import pprint
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


def fill_process_running(repos: List[Repo], action):
    procs_by_name = {}
    for proc in psutil.process_iter(attrs=None, ad_value=None):
        d = proc.as_dict(attrs=['pid', 'ppid', 'name', 'cwd', 'exe', 'username', 'cmdline', 'create_time', 'environ'],
                         ad_value=None)
        if 'username' in d and d.get('cwd', None):
            # print(f'{proc.name()} {proc.pid} {proc.ppid()} {cmd}')
            # pprint(d)
            # print(proc.cmdline())
            # line = proc.cmdline()
            for repo in repos:
                repo_dir = base_url / repo.directory

                for process in repo.processes:
                    # cmd_pattern = process['cmdPattern']
                    # index = cmd_pattern['index']
                    # if len(line) > index and cmd_pattern['pattern'] in line[index]:
                    name = process.name
                    # print(Path(d['cwd']))
                    # print(p)
                    if Path(d['cwd']).samefile(repo_dir) and match_cmd(process.cmd, d['cmdline']):
                        if name not in procs_by_name:
                            procs_by_name[name] = dict(process=process, procs=[])
                        d['proc'] = proc
                        procs_by_name[name]['procs'].append(d)

    print('############### procs_by_name')
    pprint(procs_by_name.keys())

    for name, info in procs_by_name.items():
        root = find_root(info['procs'])
        action(info['process'], root, root['proc'])


def dump_processes(dirs: List[Path]):
    for proc in psutil.process_iter(attrs=None, ad_value=None):
        proc: psutil.Process = proc
        d = proc.as_dict(attrs=['pid', 'ppid', 'name', 'cwd', 'exe', 'username', 'cmdline', 'create_time'],
                         ad_value=None)
        # d = proc.as_dict(ad_value=None)
        if 'username' in d and d.get('cwd', None) and Path(d['cwd']) in dirs:
            pprint(d)


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


def git_fetch(repo: Repo) -> str:
    """
    git fetch
    """
    git_dir = base_url / repo.directory
    logger.debug(git_dir)
    proc = subprocess.run(
        [git_cmd, 'fetch'],
        cwd=git_dir.as_posix(),
        capture_output=True)

    message = str(proc.stdout, encoding='ascii').rstrip()

    # if repo.git_tag != target_tag:
    #     proc = subprocess.run(
    #         [git_cmd, 'checkout', target_tag],
    #         cwd=git_dir.as_posix(),
    #         capture_output=True)
    #     message += '\n' + str(proc.stdout, encoding='ascii').rstrip()

    return message


def run(cwd: Path, cmd: List[str]):
    logger.debug(cwd)
    kwargs = {}
    kwargs.update(start_new_session=True)
    logger.error('Rename foo....')
    print('##############>')
    subprocess.Popen(
        cmd,
        stdout=open('foo.out', 'w'),
        stderr=open('foo.err', 'w'),
        # stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        cwd=cwd.as_posix(),
        **kwargs)
    print('<##############')


def kill(repos: List[Repo], repo_id: str, process_id: str):

    def kill_callback(process: Process, info, proc):
        if process.name != process_id:
            return
        logger.warning(f'Killing {process_id} {info["pid"]}')
        proc.terminate()
        gone, alive = psutil.wait_procs([proc], timeout=3, callback=None)
        for p in alive:
            p.kill()

    fill_process_running(repos, kill_callback)


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
    run(base_url / repo.directory, procs[0].cmd)


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


def match_cmd(cmd1: List[str], cmd2: List[str]) -> bool:
    return cmd1 == cmd2

    # cmd = ['bash', 'foo.sh']
    # Windows =>
    #    Parent: ['bash', 'foo.sh']
    #        Child:  ['C:\\WINDOWS\\system32\\wsl.exe', '-e', '/bin/bash', 'foo.sh']
    # Unix => ['bash', 'foo.sh']

    # if len(cmd1) > len(cmd2):
    #     cmd1 = cmd1[len(cmd1) - len(cmd2):]
    # elif len(cmd2) > len(cmd1):
    #     cmd2 = cmd2[len(cmd2) - len(cmd1):]
    #
    # if cmd1[0] != 'bash' and not re.match(r'.*/bash$', cmd1[0]):
    #     return False
    #
    # if cmd2[0] != 'bash' and not re.match(r'.*/bash$', cmd2[0]):
    #     return False
    #
    # return cmd1[1:] == cmd2[1:]
