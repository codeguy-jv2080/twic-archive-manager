from __future__ import annotations

import threading
import webbrowser

import uvicorn

from .main import app


HOST = "127.0.0.1"
PORT = 8765


def main() -> None:
    threading.Timer(0.75, lambda: webbrowser.open(f"http://{HOST}:{PORT}")).start()
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
