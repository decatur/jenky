import os
import sys
import time
import traceback
import datetime
import logging.handlers

print(os.environ['JENKY_LOG_FILE'])
print(os.environ['JENKY_APP_VERSION'])

logger = logging.getLogger()
handler = logging.handlers.RotatingFileHandler(
    filename=os.environ['JENKY_LOG_FILE'], mode='a', maxBytes=10*1024, backupCount=1)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

logger.info(f"App version is {os.environ['JENKY_APP_VERSION']}")


now = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
logger.info(f'Start at {now}')
logger.info(sys.path)

logger.info(sys.stdin.readline())
handler.flush()

for i in range(10):
    msg = f'index {i}'
    print(msg)
    sys.stdout.flush()
    logger.info(msg)
    time.sleep(1)
    try:
        if i % 4 == 0:
            assert False, 'willfully fail to test stderr'
    except AssertionError as e:
        print(f'Error: {repr(e)}', file=sys.stderr)
        logger.error(f'Error: {repr(e)}')
        traceback.print_exc()

    print()
    handler.flush()

logger.info('Process exits...')
print('Process exits...')

