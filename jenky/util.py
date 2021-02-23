# Note: FastApi does not support asyncio subprocesses, so do not use it!
import json
import logging
import os
from pathlib import Path
from typing import List, Tuple, Optional
import subprocess

import psutil
from pydantic import BaseModel, Field

logger = logging.getLogger()

# git_cmd = 'C:/ws/tools/PortableGit/bin/git.exe'
# git_cmd = 'git'
git_cmd: str = ''
git_version: str = ''


class Process(BaseModel):
    name: str
    cmd: List[str]
    env: dict
    running: bool
    create_time: float = Field(..., alias='createTime')
    service_url: Optional[str] = Field(alias='serviceUrl')


class Repo(BaseModel):
    repoName: str
    directory: Path
    git_tag: str = Field(..., alias='gitRef')
    git_refs: List[dict] = Field(..., alias='gitRefs')
    git_message: str = Field(..., alias='gitMessage')
    processes: List[Process]
    remote_url: Optional[str] = Field(alias='remoteUrl')


class Config(BaseModel):
    app_name: str = Field(..., alias='appName')
    repos: List[Repo]


def git_support(_git_cmd: str):
    global git_cmd, git_version
    git_cmd = _git_cmd
    try:
        proc = subprocess.run([git_cmd, '--version'], capture_output=True)
        git_version = str(proc.stdout, encoding='utf8')
    except OSError as e:
        logger.warning(str(e))


def is_git_repo(repo: Repo):
    return git_version and (repo.directory / '.git').is_dir()


def running_processes(repos: List[Repo]):
    for repo in repos:
        for proc in repo.processes:
            proc.running = False
            proc.create_time = None
            pid_file = repo.directory / (proc.name + '.pid')
            logger.debug(f'{pid_file}')
            if not pid_file.exists():
                logger.debug(f'Skipping {pid_file}')
                continue

            try:
                pid = int(pid_file.read_text())
            except Exception as e:
                logger.exception(f'Reading pid file {pid_file}')
                raise e

            try:
                p = psutil.Process(pid)
                proc.running = p.is_running()
                if proc.running and p.status() == psutil.STATUS_ZOMBIE:
                    # This happens whenever the process terminated but its creator did not because we do not wait.
                    # p.terminate()
                    p.wait()
                    proc.running = False
                proc.create_time = p.create_time()
                if proc.running:
                    try:
                        # pprint(p.environ())
                        proc.running = (p.environ().get('JENKY_NAME', '') == proc.name)
                    except psutil.AccessDenied:
                        proc.running = False
            except psutil.NoSuchProcess:
                logger.debug(f'No such proccess {pid}')
                proc.running = False


def git_refs(git_dir: Path) -> Tuple[str, List[dict]]:
    logger.debug(git_dir)
    proc = subprocess.run(
        [git_cmd, 'for-each-ref', '--sort', '-creatordate', "--format",
         """{
          "refName": "%(refname)",
          "creatorDate": "%(creatordate:iso-strict)",
          "isHead": "%(HEAD)"
        },"""],
        cwd=git_dir.as_posix(),
        capture_output=True)

    if proc.stderr:
        raise OSError(str(proc.stderr, encoding='utf8'))

    output = str(proc.stdout, encoding='utf8')
    refs = json.loads(f'[{output} null]')[:-1]
    head_refs = [ref for ref in refs if ref['isHead'] == '*']
    if not head_refs:
        proc = subprocess.run(
            [git_cmd, 'tag', '--points-at', 'HEAD'],
            cwd=git_dir.as_posix(),
            capture_output=True)

        if proc.stderr:
            raise OSError(str(proc.stderr, encoding='utf8'))

        head_ref = str(proc.stdout, encoding='utf8')
    else:
        # This would be a "git rev-parse --abbrev-ref HEAD"
        head_ref = head_refs[0]['refName']

    return head_ref, refs


def fill_git_refs(repo: Repo):
    git_dir = repo.directory
    repo.git_tag, repo.git_refs = git_refs(git_dir)


def git_fetch(repo: Repo) -> str:
    """
    git pull
    """
    git_dir = repo.directory
    messages = []
    cmd = [git_cmd, 'fetch', '--all', '--tags']
    logger.debug(f'{git_dir} {cmd}')
    proc = subprocess.run(cmd, cwd=git_dir.as_posix(), capture_output=True)
    messages.append(str(proc.stderr, encoding='ascii').rstrip())
    messages.append(str(proc.stdout, encoding='ascii').rstrip())

    # TODO: This will fail if we are detached.
    cmd = [git_cmd, 'merge']
    logger.debug(f'{git_dir} {cmd}')
    proc = subprocess.run(cmd, cwd=git_dir.as_posix(), capture_output=True)
    messages.append(str(proc.stderr, encoding='ascii').rstrip())
    messages.append(str(proc.stdout, encoding='ascii').rstrip())

    return '\n'.join(messages)


def git_checkout(repo: Repo, git_ref: str) -> str:
    """
    git_ref is of the form refs/heads/main or refs/tags/0.0.3
    """
    git_dir = repo.directory
    messages = []

    is_branch = git_ref.startswith('refs/heads/')
    target = git_ref
    if is_branch:
        # We need the branch name
        target = git_ref.split('/')[-1]

    cmd = [git_cmd, 'checkout', target]
    logger.debug(f'{git_dir} {cmd}')
    proc = subprocess.run(cmd, cwd=git_dir.as_posix(), capture_output=True)
    messages.append(str(proc.stderr, encoding='ascii').rstrip())
    messages.append(str(proc.stdout, encoding='ascii').rstrip())
    if proc.returncode == 1:
        return '\n'.join(messages)

    if is_branch:
        cmd = [git_cmd, 'pull']
        logger.debug(f'{git_dir} {cmd}')
        proc = subprocess.run(cmd, cwd=git_dir.as_posix(), capture_output=True)
        messages.append(str(proc.stderr, encoding='ascii').rstrip())
        messages.append(str(proc.stdout, encoding='ascii').rstrip())

    return '\n'.join(messages)


def run(name: str, cwd: Path, cmd: List[str], env: dict):
    my_env = os.environ

    if cmd[0] == 'python':
        executable = 'python'
        if os.name == 'nt':
            exe = 'venv/Scripts/python.exe'
            if os.access(exe, os.X_OK):
                executable = exe
            my_env['PYTHONPATH'] = 'venv/Lib/site-packages'
        elif os.name == 'posix':
            exe = 'venv/bin/python'
            if os.access(exe, os.X_OK):
                executable = exe
            my_env['PYTHONPATH'] = 'venv/lib/python3.8/site-packages'
        else:
            assert False, 'Unsupported os ' + os.name

        cmd = [executable] + cmd[1:]

    logger.debug(f'Running: {" ".join(cmd)}')
    logger.info(f'PYTHONPATH: {my_env["PYTHONPATH"]}')

    # my_env['PYTHONPATH'] += ';' + env['PYTHONPATH']
    assert 'PYTHONPATH' not in env
    my_env.update(env)
    my_env['JENKY_NAME'] = name
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
    # creationflags = subprocess.DETACHED_PROCESS  # Opens console window
    # creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW # Also opens console window
    # creationflags = subprocess.CREATE_BREAKAWAY_FROM_JOB
    # creationflags = subprocess.CREATE_NEW_CONSOLE #| subprocess.CREATE_NEW_PROCESS_GROUP
    kwargs['close_fds']: True
    out_file = cwd / f'{name}.out'
    out_file.unlink(missing_ok=True)
    stdout = open(out_file.as_posix(), 'w')

    if os.name == 'nt':
        pass
        # kwargs.update(creationflags=creationflags)
        # kwargs['close_fds']: True
    else:
        # This prevents that killing this process will kill the child process.
        kwargs.update(start_new_session=True)

    popen = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=stdout,
        stderr=subprocess.STDOUT,
        cwd=cwd.absolute(),
        env=my_env,
        **kwargs)

    pid_file = cwd / (name + '.pid')
    pid_file.write_text(str(popen.pid))

    del popen


def kill(repos: List[Repo], repo_id: str, process_id: str) -> bool:
    repo = repo_by_id(repos, repo_id)
    procs = [proc for proc in repo.processes if proc.name == process_id]
    if not procs:
        raise ValueError(repo_id)
    proc = procs[0]
    pid_file = repo.directory / (proc.name + '.pid')
    pid = int(pid_file.read_text())
    pid_file.unlink()

    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        logger.warning(f'No such process with pid {pid}')
        return False

    proc.terminate()
    # We need to wait unless a zombie stays in process list!
    gone, alive = psutil.wait_procs([proc], timeout=3, callback=None)
    for p in alive:
        p.kill()

    return True


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
    run(proc.name, repo.directory, proc.cmd, proc.env)


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


def is_file(p: Path) -> bool:
    try:
        return p.is_file()
    except PermissionError:
        return False


def collect_repos(repos_base: Path) -> List[Repo]:
    repos: List[Repo] = []
    logger.info(f'Collect repos in {repos_base}')
    for repo_dir in [f for f in repos_base.iterdir() if f.is_dir()]:
        config_file = repo_dir / 'jenky_config.json'
        if is_file(config_file):
            logger.info(f'Collecting {repo_dir}')

            data = json.loads(config_file.read_text(encoding='utf8'))
            if 'directory' in data:
                data['directory'] = (repo_dir / data['directory']).resolve()
            else:
                data['directory'] = repo_dir

            data["gitRef"] = ""
            data["gitRefs"] = []
            data["gitMessage"] = ""

            repos.append(Repo.parse_obj(data))
    return repos
