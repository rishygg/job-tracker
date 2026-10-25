"""Start the Job Tracker:  python -m jobtracker  (then open http://localhost:8501)."""

from __future__ import annotations

import argparse
import threading
import webbrowser


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Job Tracker web app.")
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-browser", action="store_true", help="Don't open a browser tab.")
    args = parser.parse_args()

    import uvicorn

    from .api import WEB_DIR, create_app

    if not (WEB_DIR / "index.html").exists():
        print("The web interface hasn't been built. Run `npm install && npm run build` in frontend/.")
    url = f"http://localhost:{args.port}"
    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    print(f"Job Tracker running at {url}  (press Ctrl+C to stop)")
    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
