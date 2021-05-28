import logging
from pathlib import Path

import persistqueue


class PersistHandler(logging.Handler):
    def __init__(self, cache_path: Path):
        super().__init__()
        print(f'cache_path {cache_path.as_posix()}')
        self.queue = persistqueue.SQLiteQueue(cache_path, auto_commit=True)
        self.formatter = logging.Formatter()

    def emit(self, record: logging.LogRecord) -> None:
        delattr(record, 'process')
        delattr(record, 'processName')
        delattr(record, 'thread')
        delattr(record, 'threadName')
        delattr(record, 'msecs')
        delattr(record, 'relativeCreated')

        if record.exc_info:
            record.exc_text = self.formatter.formatException(record.exc_info)
        else:
            delattr(record, 'exc_text')
        delattr(record, 'exc_info')

        if record.stack_info is None:
            delattr(record, 'stack_info')

        if not record.args:
            delattr(record, 'args')

        self.queue.put(record.__dict__)
        # pprint(record.__dict__)