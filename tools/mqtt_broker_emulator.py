from __future__ import annotations

import argparse
import json
import socketserver
from datetime import datetime, timezone
from pathlib import Path


def read_packet(sock) -> tuple[int, bytes] | None:
    first = sock.recv(1)
    if not first:
        return None

    multiplier = 1
    remaining_length = 0
    while True:
        raw = sock.recv(1)
        if not raw:
            return None
        encoded = raw[0]
        remaining_length += (encoded & 127) * multiplier
        if (encoded & 128) == 0:
            break
        multiplier *= 128
        if multiplier > 128 * 128 * 128:
            raise ValueError("Invalid MQTT remaining length")

    body = bytearray()
    while len(body) < remaining_length:
        chunk = sock.recv(remaining_length - len(body))
        if not chunk:
            raise ConnectionError("Client closed MQTT packet early")
        body.extend(chunk)
    return first[0], bytes(body)


def parse_mqtt_string(data: bytes, offset: int) -> tuple[str, int]:
    if offset + 2 > len(data):
        raise ValueError("MQTT string length is missing")
    length = (data[offset] << 8) + data[offset + 1]
    offset += 2
    value = data[offset : offset + length].decode("utf-8")
    return value, offset + length


class MqttBrokerHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        while True:
            packet = read_packet(self.request)
            if packet is None:
                return

            header, body = packet
            packet_type = header & 0xF0
            if packet_type == 0x10:
                self.server.log_entry(  # type: ignore[attr-defined]
                    {
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "kind": "connect",
                        "client": self.client_address[0],
                    }
                )
                self.request.sendall(bytes([0x20, 0x02, 0x00, 0x00]))
            elif packet_type == 0x30:
                topic, offset = parse_mqtt_string(body, 0)
                payload = body[offset:].decode("utf-8", errors="replace")
                self.server.log_entry(  # type: ignore[attr-defined]
                    {
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "kind": "publish",
                        "topic": topic,
                        "payload": payload,
                        "retain": bool(header & 0x01),
                        "client": self.client_address[0],
                    }
                )
            elif packet_type == 0xE0:
                return


class MqttBrokerServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], log_path: Path):
        super().__init__(server_address, MqttBrokerHandler)
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text("", encoding="utf-8")

    def log_entry(self, entry: dict[str, object]) -> None:
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Minimal MQTT 3.1.1 broker emulator for CALHouse tests.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18883)
    parser.add_argument("--log", default="tools/mqtt_broker_requests.jsonl")
    args = parser.parse_args()

    server = MqttBrokerServer((args.host, args.port), Path(args.log))
    print(f"MQTT broker emulator listening on {args.host}:{args.port}; log={args.log}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
