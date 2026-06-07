from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


class TasmotaEmulatorHandler(BaseHTTPRequestHandler):
    server_version = "CALHouseTasmotaEmulator/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        cmnd = (query.get("cmnd") or [""])[0]
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "method": "GET",
            "path": parsed.path,
            "query": {key: values[0] if len(values) == 1 else values for key, values in query.items()},
            "cmnd": cmnd,
            "client": self.client_address[0],
        }
        self.server.log_request_entry(entry)  # type: ignore[attr-defined]

        payload = {
            "POWER": "ON" if cmnd.lower() == "power on" else "OFF" if cmnd.lower() == "power off" else cmnd,
            "Command": cmnd,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


class TasmotaEmulatorServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], log_path: Path):
        super().__init__(server_address, TasmotaEmulatorHandler)
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text("", encoding="utf-8")

    def log_request_entry(self, entry: dict[str, object]) -> None:
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Minimal local Tasmota HTTP API emulator for CALHouse tests.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--log", default="tools/tasmota_emulator_requests.jsonl")
    args = parser.parse_args()

    server = TasmotaEmulatorServer((args.host, args.port), Path(args.log))
    print(f"Tasmota emulator listening on http://{args.host}:{args.port}; log={args.log}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
