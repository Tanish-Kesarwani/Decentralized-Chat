# check_entry.py - safe script that prepends Python 3.12 shim before importing web3
import inspect
if not hasattr(inspect, "getargspec"):
    from collections import namedtuple
    ArgSpec = namedtuple("ArgSpec", "args varargs keywords defaults")
    def getargspec(func):
        return ArgSpec(*inspect.getfullargspec(func)[:4])
    inspect.getargspec = getargspec

from web3 import Web3
import json, sys

try:
    w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:8545'))
    info = json.load(open('contract_info.json'))
    c = w3.eth.contract(address=info['address'], abi=info['abi'])
    n = c.functions.entriesCount().call()
    print('entries:', n)
    if n > 0:
        signer, h, ts = c.functions.getEntry(n-1).call()
        print('signer:', signer)
        if isinstance(h, (bytes, bytearray)):
            print('hash:', '0x' + h.hex())
        else:
            print('hash:', h)
        print('timestamp:', ts)
except FileNotFoundError as e:
    print("contract_info.json not found in python/ — run deploy.js to write it.", file=sys.stderr)
    raise
except Exception as e:
    print("Error querying contract:", e, file=sys.stderr)
    raise
