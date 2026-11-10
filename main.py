from app.app import create_app
from app.core import ahnx_server_config
import uvicorn

app = create_app()
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=ahnx_server_config.environment.listen_host,
        port=ahnx_server_config.environment.port,
        reload=ahnx_server_config.environment.reload
    )
