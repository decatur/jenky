import subprocess
import sys
import time
from pprint import pprint

kwargs = {}
if sys.platform == 'win32':
    # from msdn [1]
    CREATE_NEW_PROCESS_GROUP = 0x00000200  # note: could get it from subprocess
    DETACHED_PROCESS = 0x00000008  # 0x8 | 0x200 == 0x208
    DETACHED_PROCESS = getattr(subprocess, 'CREATE_BREAKAWAY_FROM_JOB', 0x00000008)
    # startupinfo = subprocess.STARTUPINFO()
    # startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    # kwargs['startupinfo'] = startupinfo

    #kwargs.update(creationflags=subprocess.CREATE_NO_WINDOW)  #CREATE_NEW_PROCESS_GROUP DETACHED_PROCESS | subprocess.CREATE_BREAKAWAY_FROM_JOB)

else:  # Python 3.2+ and Unix
    kwargs.update(start_new_session=True)

pprint(kwargs)

f = open('foo.log', 'w')
popen = subprocess.Popen(
    # ['venv/Scripts/python.exe', 'foo.py'],
    ['bash', 'p.sh'],
    stdout=f,
    #stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    **kwargs)

print('Sleeping .....')
# time.sleep(10)