# --- Python 3.12 compatibility shim for old parsimonious library ---
import inspect
if not hasattr(inspect, "getargspec"):
    from collections import namedtuple
    ArgSpec = namedtuple("ArgSpec", "args varargs keywords defaults")
    def getargspec(func):
        return ArgSpec(*inspect.getfullargspec(func)[:4])
    inspect.getargspec = getargspec
# ------------------------------------------------------------------


import socket
import threading
import hashlib
import time
import json
from web3 import Web3



# Server config
LISTEN_HOST = '0.0.0.0'
LISTEN_PORT = 9001

# Path to contract info (written by deploy script)
CONTRACT_INFO_PATH = 'contract_info.json'

# Optionally load contract info to enable on-chain verification
try:
    with open(CONTRACT_INFO_PATH, 'r') as f:
        contract_info = json.load(f)
        CONTRACT_ADDRESS = contract_info.get('address')
        CONTRACT_ABI = contract_info.get('abi')
except FileNotFoundError:
    CONTRACT_ADDRESS = None
    CONTRACT_ABI = None

w3 = None
contract = None
if CONTRACT_ADDRESS and CONTRACT_ABI:
    # provider not strictly required for server unless verifying on-chain
    w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:8545'))
    contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)

def handle_client(conn, addr):
    try:
        print(f"Connected: {addr}")
        data = conn.recv(65536)
        if not data:
            return
        payload = data.decode('utf-8')
        # Expecting simple payload: message||timestamp||senderAddr
        parts = payload.split('||')
        if len(parts) >= 2:
            message = parts[0]
            ts = int(parts[1])
            sender = parts[2] if len(parts) >= 3 else 'unknown'
        else:
            message = payload
            ts = int(time.time())
            sender = 'unknown'

        print(f"[{time.ctime(ts)}] From {sender}@{addr}: {message}")

        # compute hash locally (for verification demo)
        digest = hashlib.sha256((message + str(ts)).encode()).hexdigest()
        print("Computed SHA256:", digest)

        # If contract is available, fetch last entry and compare (optional)
        if contract:
            try:
                total = contract.functions.entriesCount().call()
                if total > 0:
                    onchain = contract.functions.getEntry(total - 1).call()
                    on_sender = onchain[0]
                    # onchain[1] may be bytes; convert to hex string with 0x prefix
                    on_hash = onchain[1].hex() if isinstance(onchain[1], bytes) else onchain[1]
                    on_ts = onchain[2]
                    print("On-chain latest entry:", on_sender, on_hash, on_ts)
            except Exception as e:
                print('Failed to read contract:', e)

        conn.send(f"ACK||{ts}".encode())
    except Exception as e:
        print("Error handling client:", e)
    finally:
        conn.close()

def run_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((LISTEN_HOST, LISTEN_PORT))
        s.listen(5)
        print("Server listening on", LISTEN_HOST, LISTEN_PORT)
        while True:
            conn, addr = s.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == '__main__':
    run_server()
