from __future__ import annotations

import argparse
import json
import socketserver
from datetime import datetime, timezone
from pathlib import Path


class CustomTcpHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        self.request.settimeout(3)
        chunks: list[bytes] = []
        while True:
            try:
                chunk = self.request.recv(4096)
            except TimeoutError:
                break
            if not chunk:
                break
            chunks.append(chunk)
            if len(b"".join(chunks)) >= 8192:
                break

        payload = b"".join(chunks).decode("utf-8", errors="replace")
        self.server.log_entry(  # type: ignore[attr-defined]
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "client": self.client_address[0],
                "payload": payload,
            }
        )
        try:
            self.request.sendall(b"OK\n")
        except OSError:
            pass


class CustomTcpServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], log_path: Path):
        super().__init__(server_address, CustomTcpHandler)
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text("", encoding="utf-8")

    def log_entry(self, entry: dict[str, object]) -> None:
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Minimal TCP device emulator for CALHouse custom_tcp tests.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=19001)
    parser.add_argument("--log", default="tools/custom_tcp_requests.jsonl")
    args = parser.parse_args()

    server = CustomTcpServer((args.host, args.port), Path(args.log))
    print(f"Custom TCP emulator listening on {args.host}:{args.port}; log={args.log}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
