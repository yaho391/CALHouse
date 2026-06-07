from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


class ShellyEmulatorHandler(BaseHTTPRequestHandler):
    server_version = "CALHouseShellyEmulator/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "method": "GET",
            "path": parsed.path,
            "query": {key: values[0] if len(values) == 1 else values for key, values in query.items()},
            "client": self.client_address[0],
            "authorization": self.headers.get("Authorization", ""),
        }
        self.server.log_request_entry(entry)  # type: ignore[attr-defined]

        if parsed.path.lower() == "/rpc/switch.set":
            is_on = (query.get("on") or ["false"])[0].lower() == "true"
            payload = {"was_on": not is_on, "id": int((query.get("id") or ["0"])[0])}
        elif parsed.path.lower().startswith("/relay/"):
            is_on = (query.get("turn") or ["off"])[0].lower() == "on"
            payload = {"ison": is_on}
        else:
            payload = {"ok": True}

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


class ShellyEmulatorServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], log_path: Path):
        super().__init__(server_address, ShellyEmulatorHandler)
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text("", encoding="utf-8")

    def log_request_entry(self, entry: dict[str, object]) -> None:
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Minimal local Shelly HTTP API emulator for CALHouse tests.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8089)
    parser.add_argument("--log", default="tools/shelly_emulator_requests.jsonl")
    args = parser.parse_args()

    server = ShellyEmulatorServer((args.host, args.port), Path(args.log))
    print(f"Shelly emulator listening on http://{args.host}:{args.port}; log={args.log}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
