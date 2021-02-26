# This script tests if a subprocess is kept alive after its creator (i.e. this script) exits.

import subprocess
import sys
import time
from pprint import pprint

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
# kwargs['close_fds']: True

# kwargs = {}
# if sys.platform == 'win32':
#     # from msdn [1]
#     CREATE_NEW_PROCESS_GROUP = 0x00000200  # note: could get it from subprocess
#     DETACHED_PROCESS = 0x00000008  # 0x8 | 0x200 == 0x208
#     DETACHED_PROCESS = getattr(subprocess, 'CREATE_BREAKAWAY_FROM_JOB', 0x00000008)
#     # startupinfo = subprocess.STARTUPINFO()
#     # startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
#     # kwargs['startupinfo'] = startupinfo
#
#     #kwargs.update(creationflags=subprocess.CREATE_NO_WINDOW)  #CREATE_NEW_PROCESS_GROUP DETACHED_PROCESS | subprocess.CREATE_BREAKAWAY_FROM_JOB)
#
# else:  # Python 3.2+ and Unix
#     kwargs.update(start_new_session=True)
#
# pprint(kwargs)
# kwargs = dict(close_fds=True)

pyvenv = {k.strip():v.strip() for k, v in (l.split('=') for l in open('venv/pyvenv.cfg', 'r'))}

f = open('scripts/test_subprocess.log', 'w')
popen = subprocess.Popen(
    [pyvenv['home'] + '/python.exe', 'scripts/sample.py'],
    stdout=f,
    # stdin=subprocess.DEVNULL,
    stderr=subprocess.STDOUT
)

print(f'Started process with pid {popen.pid}')
# Use powershell> get-process python
#print('Sleeping .....'); time.sleep(10)