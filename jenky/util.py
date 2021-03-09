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


def running_process(proc: Process, directory: Path) -> Optional[psutil.Process]:
    pid_file = directory / (proc.name + '.pid')
    logger.debug(f'Reading {pid_file}')

    if not pid_file.exists():
        logger.debug(f'Skipping {pid_file}')
        return None

    try:
        pid = int(pid_file.read_text())
    except Exception as e:
        logger.exception(f'Reading pid file {pid_file}')
        raise e

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
        # pprint(p.environ())
        if (p.environ().get('JENKY_NAME', '') == proc.name):
            return p
    except psutil.AccessDenied:
        pass

    return None


def running_processes(repos: List[Repo]):
    for repo in repos:
        for proc in repo.processes:
            p = running_process(proc, repo.directory)
            if p:
                proc.running = True
                proc.create_time = p.create_time()
            else:
                proc.running = False
                proc.create_time = None


def git_refs(git_dir: Path) -> Tuple[str, List[dict]]:
    logger.debug(git_dir)
    # TODO: git ls-remote --refs --quiet --symref
    # But note that we cannot get creatorDate, nor sort by it!
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


def git_fetch(repo: Repo) -> List[str]:
    git_dir = repo.directory
    messages = []
    cmd = [git_cmd, 'fetch', '--tags']
    logger.debug(f'{git_dir} {cmd}')
    proc = subprocess.run(cmd, cwd=git_dir.as_posix(), capture_output=True)
    messages.append(str(proc.stderr, encoding='ascii').rstrip())
    messages.append(str(proc.stdout, encoding='ascii').rstrip())

    return messages


def get_sha(git_dir: Path, file: Path) -> str:
    cmd = [git_cmd, "ls-files", "-s", file.as_posix()]
    proc = subprocess.run(cmd, cwd=git_dir.as_posix(), capture_output=True)
    line = str(proc.stdout, encoding='ascii').rstrip()
    # Output format is
    #    '100644 3fff12262ed377d9023c70f13f93ebd6b0f9dc46 0	filename'
    return line.split()[1]


def git_checkout(repo: Repo, git_ref: str) -> str:
    """
    git_ref is of the form refs/heads/main or refs/tags/0.0.3
    """
    git_dir = repo.directory

    is_branch = git_ref.startswith('refs/heads/')
    target = git_ref
    if is_branch:
        # We need the branch name
        target = git_ref.split('/')[-1]

    sha_before = get_sha(git_dir, Path('requirements.txt'))

    cmd = [git_cmd, 'checkout', target]
    logger.debug(f'{git_dir} {cmd}')
    proc = subprocess.run(cmd, cwd=git_dir.as_posix(), capture_output=True)
    messages = []
    messages.append(str(proc.stderr, encoding='ascii').rstrip())
    messages.append(str(proc.stdout, encoding='ascii').rstrip())
    if proc.returncode == 1:
        pass
    elif is_branch:
        cmd = [git_cmd, 'merge']
        logger.debug(f'{git_dir} {cmd}')
        proc = subprocess.run(cmd, cwd=git_dir.as_posix(), capture_output=True)
        messages.append(str(proc.stderr, encoding='ascii').rstrip())
        messages.append(str(proc.stdout, encoding='ascii').rstrip())

    sha_after = get_sha(git_dir, Path('requirements.txt'))
    if sha_after != sha_before:
        messages.append('Warning: requirements.txt did change!')

    return '\n'.join(messages)


def run(name: str, cwd: Path, cmd: List[str], env: dict):
    my_env = os.environ.copy()
    my_env.update(env)
    my_env['JENKY_NAME'] = name

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
    logger.info(f'PYTHONPATH: {my_env["PYTHONPATH"]}')

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

    pid_file = cwd / (name + '.pid')
    pid_file.write_text(str(popen.pid))

    del popen  # Voodoo


def kill(repos: List[Repo], repo_id: str, process_id: str) -> bool:
    repo = repo_by_id(repos, repo_id)
    procs = [proc for proc in repo.processes if proc.name == process_id]
    if not procs:
        raise ValueError(repo_id)
    proc = procs[0]
    pid_file = repo.directory / (proc.name + '.pid')
    pid = int(pid_file.read_text())
    pid_file.unlink()

    p = running_process(proc, repo.directory)
    if p:
        p.terminate()
        # We need to wait unless a zombie stays in process list!
        gone, alive = psutil.wait_procs([p], timeout=3, callback=None)
        for process in alive:
            process.kill()

        return True
    return False


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
    p = running_process(proc, repo.directory)
    assert p is None
    run(proc.name, repo.directory, proc.cmd, proc.env)


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


def auto_run_processes(repos: List[Repo]):
    for repo in repos:
        for proc in repo.processes:
            if proc.running:
                p = running_process(proc, repo.directory)
                if not p:
                    logger.info(f'Auto-running {repo.repoName}.{proc.name}')
                    run(proc.name, repo.directory, proc.cmd, proc.env)
                    continue
            logger.info(f'Not Auto-running {repo.repoName}.{proc.name}')
