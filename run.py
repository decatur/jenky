import logging
from typing import List

import uvicorn

from jenky.logging import PersistHandler
from jenky.server import app
from jenky import util

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


def my_handler(records: List[dict]):
    for record in records:
        util.list_handler.emit(PersistHandler.record_from_dict(record))


host, port, config = util.parse_args()
app.state.config = config

util.log_handler = my_handler
uvicorn.run(app, host=host, port=port)
