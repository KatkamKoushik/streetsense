import socket
import asyncio
import pytest
import pytest_asyncio
import uvicorn
from app.main import app


def get_free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest_asyncio.fixture
async def live_server():
    port = get_free_port()
    config = uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    # Wait for server to bind and start listening
    for _ in range(50):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("127.0.0.1", port))
            s.close()
            break
        except Exception:
            await asyncio.sleep(0.05)

    ws_url = f"ws://127.0.0.1:{port}"
    http_url = f"http://127.0.0.1:{port}"
    yield {"ws_url": ws_url, "http_url": http_url, "port": port}

    server.should_exit = True
    await task

