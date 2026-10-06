"""Local site for looking up public App Store reviews."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from app_review.itunes import AppNotFound, InvalidAppId, ItunesError
from app_review.service import load_reviews
from app_review.translate import LANGUAGES, TranslateError, translate_texts

STATIC_DIR = Path(__file__).resolve().parent / "static"
MAX_BODY = 16_384
MAX_TRANSLATE_BODY = 400_000

_ERROR_CODE = {
    InvalidAppId: "invalid_app",
    AppNotFound: "not_found",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Open the App Store review site")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()
    return 0


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self._send_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            return
        if path == "/favicon.ico":
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self._send_json(404, {"error": "找不到這個頁面。"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/translate":
            self._translate()
            return
        if path != "/api/reviews":
            self._send_json(404, {"error": "找不到這個頁面。"})
            return
        try:
            app = _read_app(self)
        except ValueError as error:
            self._send_json(400, {"error": str(error)})
            return
        self._stream_reviews(app)

    def _translate(self) -> None:
        try:
            payload = _read_json(self, MAX_TRANSLATE_BODY)
        except ValueError as error:
            self._send_json(400, {"error": str(error)})
            return
        target = payload.get("target")
        texts = payload.get("texts")
        if not isinstance(target, str) or target not in LANGUAGES:
            self._send_json(400, {"code": "bad_target"})
            return
        if not isinstance(texts, list) or not all(isinstance(text, str) for text in texts):
            self._send_json(400, {"code": "bad_texts"})
            return
        try:
            translations = translate_texts(texts, target)
        except TranslateError as error:
            self._send_json(502, {"code": error.code})
            return
        self._send_json(200, {"translations": translations})

    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} {fmt % args}", flush=True)

    def _stream_reviews(self, app: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

        def send(payload: dict[str, object]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode() + b"\n"
            self.wfile.write(f"{len(body):X}\r\n".encode())
            self.wfile.write(body)
            self.wfile.write(b"\r\n")
            self.wfile.flush()

        def on_status(event: dict[str, object]) -> None:
            if event.get("kind") == "fetched":
                return
            send({"type": "status", **event})

        try:
            try:
                payload = load_reviews(app, on_status=on_status)
            except ItunesError as error:
                send({"type": "error", "code": _ERROR_CODE.get(type(error), "fetch_failed")})
            except Exception:
                send({"type": "error", "code": "fetch_failed"})
            else:
                send({"type": "result", "data": payload})
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        except BrokenPipeError:
            return

    def _send_file(self, path: Path, content_type: str) -> None:
        if not path.is_file():
            self._send_json(500, {"error": "網站檔案不見了。"})
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _read_app(handler: BaseHTTPRequestHandler) -> str:
    payload = _read_json(handler, MAX_BODY)
    app = payload.get("app")
    if not isinstance(app, str) or not app.strip():
        raise ValueError("請貼上 App Store 網址或 App ID。")
    return app.strip()


def _read_json(handler: BaseHTTPRequestHandler, limit: int) -> dict[str, object]:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0 or length > limit:
        raise ValueError("請求內容不正確。")
    raw = handler.rfile.read(length)
    try:
        payload = json.loads(raw.decode())
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("請求內容不正確。") from error
    if not isinstance(payload, dict):
        raise ValueError("請求內容不正確。")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
