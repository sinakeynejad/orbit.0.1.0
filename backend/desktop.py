"""Native desktop launcher; the backend is restricted to an ephemeral loopback port."""
import os
import socket
import sys
import threading
import time
from pathlib import Path
import uvicorn
import webview
from app.api.main import create_app
from app.core.config import get_settings


def main():
    log_dir = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "DesktopAssistant"
    log_dir.mkdir(parents=True, exist_ok=True)
    if sys.stdout is None: sys.stdout = (log_dir / "desktop.log").open("a", encoding="utf-8")
    if sys.stderr is None: sys.stderr = sys.stdout
    config = get_settings()
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(config), log_level="warning", log_config=None))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    for _ in range(200):
        if server.started: break
        if not thread.is_alive(): raise RuntimeError("Backend startup failed.")
        time.sleep(0.05)
    if not server.started: raise RuntimeError("Backend startup timed out.")
    if "--smoke-test" in sys.argv:
        import urllib.request
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as response:
            assert b"root" in response.read()
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
        (config.data_dir / "smoke-test.txt").write_text("Desktop smoke test passed", encoding="utf-8")
        print("Desktop smoke test passed", flush=True)
        return
    url = f"http://127.0.0.1:{port}/#token={config.api_token.get_secret_value()}"
    webview.create_window("Orbit · Desktop Assistant", url, width=1200, height=820, min_size=(780, 600))
    try:
        webview.start(gui="edgechromium", private_mode=True)
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        if sys.stderr: sys.stderr.flush()
        raise
