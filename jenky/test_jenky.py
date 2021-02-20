import time
from pprint import pprint
from pathlib import Path
from jenky import util

config = [
    {
        "repoName": "jenky",
        "directory": "jenky",
        "gitRef": "4711",
        "gitRefs": ["..."],
        "processes": [
            {
                "name": "jenky",
                "running": None,
                "cmdPattern": {
                    "index": 1,
                    "pattern": "test_jenky"
                }
            }
        ]
    }
]


def test_fill_process_running():
    util.fill_process_running(config)
    pprint(config)


async def test_fill_tag():
    await util.fill_git_tag(config)
    pprint(config)


def test_fill_tags():
    util.fill_git_tags(config)
    pprint(config)


def test_find_root():
    procs = [
        dict(pid=1, ppid=2, info='p1'),
        dict(pid=2, ppid=3, info='p2')]
    root = util.find_root(procs)
    assert root == procs[1]

    procs = [
        dict(pid=2, ppid=3, info='p2'),
        dict(pid=1, ppid=2, info='p1')
        ]
    root = util.find_root(procs)
    assert root == procs[0]

    procs = [
        dict(pid=1, ppid=2, info='p1'),
        dict(pid=3, ppid=4, info='p2')
    ]
    try:
        root = util.find_root(procs)
        assert False
    except AssertionError:
        pass


def test_git_branches():
    branches = util.git_branches(Path('c:/ws/projects/VirtualPowerStorage'))
    pprint(branches)


def test_git_tags():
    tags = util.git_refs(Path('c:/ws/projects/VirtualPowerStorage'))
    pprint(tags)


def test_run():
    cwd = Path('.').absolute()
    util.run(cwd, ['bash', 'p.sh'])
    time.sleep(1)
    util.dump_processes([cwd])


def test_match_cmd():
    cmd1 = ['bash', 'foo.sh']
    cmd2 = [r'C:\\WINDOWS\\system32\\wsl.exe', '-e', '/bin/bash', 'foo.sh']
    assert util.match_cmd(cmd1, cmd2)


util.git_cmd = 'C:/ws/tools/PortableGit/bin/git.exe'
test_match_cmd()
