import sys
import time
import traceback
import datetime
from pprint import pprint

now = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
print(f'Start at {now}')
pprint(sys.path)

print(sys.stdin.readline())

for i in range(10):
    print(i)
    time.sleep(1)
    try:
        if i % 4 == 0:
            assert False, 'willfully fail to test stderr'
    except AssertionError as e:
        print(f'Error: {repr(e)}', file=sys.stderr)
        traceback.print_exc()
        sys.stderr.flush()

    sys.stdout.flush()

print('Process exits...')
