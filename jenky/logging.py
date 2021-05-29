# TODO: Rename?
# If an application accidentally has the jenky package folder in its search path,
# this module overrides stdlib logging package, and things fail. Which is fine, or not.
import logging
from pathlib import Path
from typing import Dict

import persistqueue


class PersistHandler(logging.Handler):
    def __init__(self, cache_path: Path):
        super().__init__()
        print(f'cache_path {cache_path.as_posix()}')
        self.queue = persistqueue.SQLiteQueue(cache_path, auto_commit=True)
        self.formatter = logging.Formatter()

    def emit(self, record: logging.LogRecord) -> None:
        self.queue.put(self.record_to_dict(record))

    def record_to_dict(self, record: logging.LogRecord) -> Dict:
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

        return record.__dict__

    @classmethod
    def record_from_dict(cls, d: Dict) -> logging.LogRecord:
        record = logging.LogRecord(
            d['name'],
            logging.__dict__[d['levelname']],
            d['pathname'],
            d['lineno'],
            d['msg'],
            args=(),
            exc_info=None,
            func=d['funcName']
        )
        record.module = d['module']
        record.created = d['created']
        if 'exc_text' in d:
            record.exc_text = d['exc_text']
        return record
