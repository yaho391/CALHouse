from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class HomeAssistantEmulatorHandler(BaseHTTPRequestHandler):
    server_version = "CALHouseHomeAssistantEmulator/1.0"

    def do_GET(self) -> None:
        self.handle_request()

    def do_POST(self) -> None:
        self.handle_request()

    def handle_request(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(content_length) if content_length > 0 else b""
        body_text = raw_body.decode("utf-8", errors="replace")
        authorization = self.headers.get("Authorization", "")
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "method": self.command,
            "path": self.path,
            "authorization": authorization,
            "body": body_text,
            "client": self.client_address[0],
        }
        self.server.log_request_entry(entry)  # type: ignore[attr-defined]

        if authorization != "Bearer test-ha-token":
            self.write_json(401, {"message": "unauthorized"})
            return

        if self.command == "GET" and self.path == "/api/states/light.kitchen":
            self.write_json(200, {"entity_id": "light.kitchen", "state": "off"})
            return

        if self.command == "POST" and self.path in {
            "/api/services/homeassistant/turn_on",
            "/api/services/homeassistant/turn_off",
        }:
            self.write_json(200, [{"entity_id": "light.kitchen", "state": "ok"}])
            return

        self.write_json(404, {"message": "not found"})

    def write_json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


class HomeAssistantEmulatorServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], log_path: Path):
        super().__init__(server_address, HomeAssistantEmulatorHandler)
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text("", encoding="utf-8")

    def log_request_entry(self, entry: dict[str, object]) -> None:
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Minimal Home Assistant REST API emulator for CALHouse tests.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8124)
    parser.add_argument("--log", default="tools/homeassistant_requests.jsonl")
    args = parser.parse_args()

    server = HomeAssistantEmulatorServer((args.host, args.port), Path(args.log))
    print(f"Home Assistant emulator listening on http://{args.host}:{args.port}; log={args.log}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
