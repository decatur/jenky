import uvicorn

from jenky.server import app
from jenky import util


host, port, config = util.parse_args()
app.state.config = config
uvicorn.run(app, host=host, port=port)
