from __future__ import annotations

import argparse
import json
import socketserver
from datetime import datetime, timezone
from pathlib import Path


class RtspCameraHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        data = bytearray()
        self.request.settimeout(5)
        while b"\r\n\r\n" not in data and len(data) < 8192:
            chunk = self.request.recv(1024)
            if not chunk:
                break
            data.extend(chunk)

        request_text = data.decode("ascii", errors="replace")
        first_line = request_text.splitlines()[0] if request_text.splitlines() else ""
        cseq = "1"
        for line in request_text.splitlines()[1:]:
            if line.lower().startswith("cseq:"):
                cseq = line.split(":", 1)[1].strip() or "1"
                break

        self.server.log_entry(  # type: ignore[attr-defined]
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "client": self.client_address[0],
                "firstLine": first_line,
                "request": request_text,
            }
        )

        response = (
            "RTSP/1.0 200 OK\r\n"
            f"CSeq: {cseq}\r\n"
            "Public: OPTIONS, DESCRIBE\r\n"
            "Server: CALHouseRtspCameraEmulator/1.0\r\n"
            "\r\n"
        )
        self.request.sendall(response.encode("ascii"))


class RtspCameraServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], log_path: Path):
        super().__init__(server_address, RtspCameraHandler)
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text("", encoding="utf-8")

    def log_entry(self, entry: dict[str, object]) -> None:
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Minimal RTSP camera emulator for CALHouse tests.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8554)
    parser.add_argument("--log", default="tools/rtsp_camera_requests.jsonl")
    args = parser.parse_args()

    server = RtspCameraServer((args.host, args.port), Path(args.log))
    print(f"RTSP camera emulator listening on rtsp://{args.host}:{args.port}; log={args.log}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
