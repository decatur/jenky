# Note: FastApi does not support asyncio subprocesses, so do not use it!
import logging
import sys
from pathlib import Path
from pprint import pprint
from typing import List, Tuple, Any
import subprocess

import psutil

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(sys.stdout))

# git_cmd = 'C:/ws/tools/PortableGit/bin/git.exe'
git_cmd = 'git'


def fill_process_running(config: List[dict], action):
    procs_by_name = {}
    for proc in psutil.process_iter(attrs=None, ad_value=None):
        d = proc.as_dict(attrs=['pid', 'ppid', 'name', 'cwd', 'exe', 'username', 'cmdline', 'create_time', 'environ'], ad_value=None)
        if 'username' in d and d.get('cwd', None):
            # print(f'{proc.name()} {proc.pid} {proc.ppid()} {cmd}')
            # pprint(d)
            # print(proc.cmdline())
            # line = proc.cmdline()
            for repo in config:
                for process in repo['processes']:
                    # cmd_pattern = process['cmdPattern']
                    # index = cmd_pattern['index']
                    #if len(line) > index and cmd_pattern['pattern'] in line[index]:
                    name = process['name']
                    p = Path(__file__).parent.parent.parent / repo['directory']
                    if Path(d['cwd']) == p and name == d['environ'].get('JENKY_PROCESS_NAME'):
                        if name not in procs_by_name:
                            procs_by_name[name] = dict(process=process, procs=[])
                        d['proc'] = proc
                        procs_by_name[name]['procs'].append(d)

    for name, info in procs_by_name.items():
        root = find_root(info['procs'])
        action(info['process'], root, root['proc'])


def dump_processes(dirs: List[Path]):
    for proc in psutil.process_iter(attrs=None, ad_value=None):
        proc: psutil.Process = proc
        d = proc.as_dict(attrs=['pid', 'ppid', 'name', 'cwd', 'exe', 'username', 'cmdline', 'create_time'], ad_value=None)
        # d = proc.as_dict(ad_value=None)
        if 'username' in d and d.get('cwd', None) and Path(d['cwd']) in dirs:
            pprint(d)


def get_process():
    for proc in psutil.process_iter(attrs=None, ad_value=None):
        print(proc)
        if proc.name() == 'python.exe':
            print(proc.cmdline())
            line = proc.cmdline()
            if len(line) == 3 and 'test' in line[2]:
                return proc


def git_tag(cwd: Path) -> str:
    p = Path(__file__).parent.parent.parent / cwd
    print(p.as_posix())
    proc = subprocess.run(
        [git_cmd, 'describe', '--tags'],
        cwd=p,
        capture_output=True)

    if proc.stderr:
        raise OSError(str(proc.stderr, encoding='ascii'))
    tag = str(proc.stdout, encoding='ascii')
    return tag


def fill_git_tag(config: List[dict]):
    for repo in config:
        try:
            repo['gitTag'] = git_tag(Path(repo['directory']))
        except OSError as e:
            if 'gitTag' in repo:
                del repo['gitTag']
            repo['gitMessage'] = str(e)


def git_tags(cwd: Path) -> List[str]:
    p = Path(__file__).parent.parent.parent / cwd
    print(p.as_posix())
    proc = subprocess.run(
        [git_cmd, 'tag', '--sort', 'version:refname'],
        cwd=p,
        capture_output=True)

    if proc.stderr:
        raise OSError(str(proc.stderr, encoding='ascii'))
    tags = str(proc.stdout, encoding='ascii').split()
    return tags


def fill_git_tags(config: List[dict]):
    for repo in config:
        try:
            repo['gitTags'] = git_tags(Path(repo['directory']))
        except OSError as e:
            repo['gitTags'] = []
            repo['gitMessage'] = str(e)


def git_pull(repo: dict, target_tag: str) -> str:
    """
    git fetch
    git checkout test
    """
    p = Path(__file__).parent.parent.parent / repo['directory']
    print(p.as_posix())
    proc = subprocess.run(
        [git_cmd, 'fetch'],
        cwd=p,
        capture_output=True)

    message = str(proc.stdout, encoding='ascii').rstrip()

    if repo['gitTag'] != target_tag:
        proc = subprocess.run(
            [git_cmd, 'checkout', target_tag],
            cwd=p,
            capture_output=True)
        message += '\n' + str(proc.stdout, encoding='ascii').rstrip()

    return message


def run(cwd: Path, cmd: List[str]):
    p = Path(__file__).parent.parent.parent / cwd
    print(p.as_posix())
    kwargs = {}
    if sys.platform == 'win32':
        # from msdn [1]
        CREATE_NEW_PROCESS_GROUP = 0x00000200  # note: could get it from subprocess
        DETACHED_PROCESS = 0x00000008  # 0x8 | 0x200 == 0x208
        DETACHED_PROCESS = getattr(subprocess, 'CREATE_BREAKAWAY_FROM_JOB', 0x00000008)
        # startupinfo = subprocess.STARTUPINFO()
        # startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        # kwargs['startupinfo'] = startupinfo

        kwargs.update(creationflags=subprocess.CREATE_NO_WINDOW)  #CREATE_NEW_PROCESS_GROUP DETACHED_PROCESS | subprocess.CREATE_BREAKAWAY_FROM_JOB)

    else:  # Python 3.2+ and Unix
        kwargs.update(start_new_session=True)

    pprint(kwargs)

    popen = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        cwd=p,
        **kwargs)
    del popen


def kill(config: List[dict], repo_id: str, process_id: str):

    def kill_callback(process, info, proc):
        logger.warning(f'Killing {process["name"]}')
        proc.terminate()
        gone, alive = psutil.wait_procs([proc], timeout=3, callback=None)
        for p in alive:
            p.kill()

    fill_process_running(config, kill_callback)


def repo_by_id(config: List[dict], repo_id: str) -> dict:
    repos = [repo for repo in config if repo['repoName'] == repo_id]
    if not repos:
        raise ValueError(repo_id)
    return repos[0]


def restart(config: List[dict], repo_id: str, process_id: str):
    repo = repo_by_id(config, repo_id)
    procs = [proc for proc in repo['processes'] if proc['name'] == process_id]
    if not procs:
        raise ValueError(repo_id)

    run(repo['directory'], procs[0]['cmd'])


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





