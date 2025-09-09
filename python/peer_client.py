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
import hashlib
import time
import json
import os
from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_defunct



# CONFIG - change only if you must
REMOTE_HOST = os.environ.get('REMOTE_HOST', '127.0.0.1')
REMOTE_PORT = int(os.environ.get('REMOTE_PORT', 9001))
RPC_URL = os.environ.get('RPC_URL', 'http://127.0.0.1:8545')
CONTRACT_INFO_PATH = 'contract_info.json'

# PRIVATE_KEY must be set as an environment variable for safety
PRIVATE_KEY = os.environ.get('PRIVATE_KEY')
if not PRIVATE_KEY:
    print('ERROR: set PRIVATE_KEY environment variable (use a local test account from Hardhat)') 
    exit(1)

# load contract info
try:
    with open(CONTRACT_INFO_PATH, 'r') as f:
        info = json.load(f)
        CONTRACT_ADDRESS = info['address']
        CONTRACT_ABI = info['abi']
except Exception as e:
    print('ERROR: contract_info.json not found or invalid. Deploy the contract first.')
    exit(1)

w3 = Web3(Web3.HTTPProvider(RPC_URL))
acct = Account.from_key(PRIVATE_KEY)
contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)

print('Using account:', acct.address)

def send_message_and_store_on_chain(message):
    # 1) prepare timestamp and payload
    ts = int(time.time())
    payload = message + '||' + str(ts) + '||' + acct.address

    # 2) send payload to remote peer via socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((REMOTE_HOST, REMOTE_PORT))
        s.send(payload.encode())
        ack = s.recv(1024).decode()
        print('Peer ack:', ack)

    # 3) compute SHA256 digest
    digest_hex = hashlib.sha256((message + str(ts)).encode()).hexdigest()
    print('SHA256 (hex):', digest_hex)

    # 4) convert to bytes32
    digest_bytes32 = Web3.toBytes(hexstr='0x' + digest_hex)

    # 5) build & sign transaction to store hash
    nonce = w3.eth.get_transaction_count(acct.address)
    tx = contract.functions.storeHash(digest_bytes32).build_transaction({
        'chainId': w3.eth.chain_id,
        'gas': 200000,
        'gasPrice': w3.toWei('1', 'gwei'),
        'nonce': nonce,
    })
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    print('Submitted tx:', tx_hash.hex())
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print('Tx mined in block', receipt.blockNumber)

    # 6) (optional) sign the digest locally as a human-readable signature
    msg = encode_defunct(hexstr='0x' + digest_hex)
    signed_msg = Account.sign_message(msg, private_key=PRIVATE_KEY)
    print('Local signature (r,s,v):', signed_msg.r, signed_msg.s, signed_msg.v)

if __name__ == '__main__':
    print('Type messages and press enter. Ctrl+C to quit.')
    try:
        while True:
            msg = input('> ')
            if not msg:
                continue
            send_message_and_store_on_chain(msg)
    except KeyboardInterrupt:
        print('\nExiting')
