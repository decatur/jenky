from pprint import pprint

from jenky import util

config = [
    {
        "repoName": "jenky",
        "directory": "jenky",
        "gitTag": "4711",
        "gitTags": ["..."],
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

test_find_root()
