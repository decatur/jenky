# Note: FastApi does not support asyncio subprocesses, so do not use it!
import json
import logging
import os
from pathlib import Path
from typing import List, Tuple, Optional
import subprocess

from pydantic import BaseModel

from jenky import util
from jenky.util import Repo

logger = logging.getLogger()

# git_cmd = 'C:/ws/tools/PortableGit/bin/git.exe'
# git_cmd = 'git'
git_cmd: str = ''
git_version: str = ''


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


class GitAction(BaseModel):
    action: str
    gitRef: Optional[str]


def register_endpoints(app, config):

    @app.get("/repos/{repo_id}")
    def get_repo(repo_id: str) -> Repo:
        repo = util.repo_by_id(config.repos, repo_id)
        if is_git_repo(repo):
            git_fetch(repo)
            repo.git_tag, repo.git_refs = git_refs(repo.directory)
        else:
            repo.git_message = 'Not a git repository'
        return repo

    @app.post("/repos/{repo_id}")
    def post_repo(repo_id: str, action: GitAction) -> dict:
        repo = util.repo_by_id(config.repos, repo_id)
        if action.action == 'checkout':
            message = git_checkout(repo, git_ref=action.gitRef)
        else:
            assert False, 'Invalid action ' + action.action

        return dict(repo_id=repo_id, action=action.action, message=message)
