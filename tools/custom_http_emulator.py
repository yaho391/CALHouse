from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


class CustomHttpEmulatorHandler(BaseHTTPRequestHandler):
    server_version = "CALHouseCustomHttpEmulator/1.0"

    def do_GET(self) -> None:
        self.handle_any()

    def do_POST(self) -> None:
        self.handle_any()

    def do_PUT(self) -> None:
        self.handle_any()

    def do_PATCH(self) -> None:
        self.handle_any()

    def handle_any(self) -> None:
        parsed = urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(content_length) if content_length > 0 else b""
        body_text = raw_body.decode("utf-8", errors="replace")
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "method": self.command,
            "path": parsed.path,
            "query": {key: values[0] if len(values) == 1 else values for key, values in parse_qs(parsed.query).items()},
            "body": body_text,
            "headers": {
                key: value
                for key, value in self.headers.items()
                if key.lower() not in {"authorization", "cookie"}
            },
            "client": self.client_address[0],
        }
        self.server.log_request_entry(entry)  # type: ignore[attr-defined]

        response_body = json.dumps({"ok": True}, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def log_message(self, format: str, *args: object) -> None:
        return


class CustomHttpEmulatorServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], log_path: Path):
        super().__init__(server_address, CustomHttpEmulatorHandler)
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text("", encoding="utf-8")

    def log_request_entry(self, entry: dict[str, object]) -> None:
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Minimal HTTP device emulator for CALHouse custom_http tests.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--log", default="tools/custom_http_requests.jsonl")
    args = parser.parse_args()

    server = CustomHttpEmulatorServer((args.host, args.port), Path(args.log))
    print(f"Custom HTTP emulator listening on http://{args.host}:{args.port}; log={args.log}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
