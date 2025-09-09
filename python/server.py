# server.py
# Phase 6-ready server: WebSocket + static index.html + /store that supports storeHashWithSig
#
# Place this at: C:\Users\Hp\Desktop\decentralized_chat\python\server.py
# Requires: aiohttp, web3 (v5), eth_account, etc. (your venv already has these)
# Make sure contract_info.json exists in the same folder (written by deploy.js)

# --- Python 3.12 compatibility shim for parsimonious (adds inspect.getargspec) ---
import inspect
if not hasattr(inspect, "getargspec"):
    from collections import namedtuple
    ArgSpec = namedtuple("ArgSpec", "args varargs keywords defaults")
    def getargspec(func):
        return ArgSpec(*inspect.getfullargspec(func)[:4])
    inspect.getargspec = getargspec
# -------------------------------------------------------------------------

import os
import json
import time
from aiohttp import web, WSMsgType, WSCloseCode
from web3 import Web3
from eth_account.messages import encode_defunct

# ---------- Configuration ----------
HTTP_HOST = '0.0.0.0'
HTTP_PORT = int(os.environ.get('HTTP_PORT', '9002'))

CONTRACT_INFO_PATH = os.path.join(os.getcwd(), 'contract_info.json')  # must exist
RPC_URL = os.environ.get('RPC_URL', 'http://127.0.0.1:8545')
SERVER_PRIVATE_KEY = os.environ.get('SERVER_PRIVATE_KEY')  # hex string '0x...'

MESSAGES_FILE = os.path.join(os.getcwd(), 'messages.json')
WS_PATH = '/ws'
# -----------------------------------

# Load contract info (address + ABI)
contract_info = {}
if os.path.exists(CONTRACT_INFO_PATH):
    with open(CONTRACT_INFO_PATH, 'r', encoding='utf-8') as f:
        contract_info = json.load(f)

CONTRACT_ADDRESS = contract_info.get('address')
CONTRACT_ABI = contract_info.get('abi')

w3 = None
contract = None
server_account = None
if CONTRACT_ADDRESS and CONTRACT_ABI and SERVER_PRIVATE_KEY:
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)
    server_account = w3.eth.account.from_key(SERVER_PRIVATE_KEY)
    print("Server will submit txs using address:", server_account.address)
else:
    print("On-chain writing not configured. To enable set SERVER_PRIVATE_KEY and ensure contract_info.json exists.")

# Ensure messages.json exists
if not os.path.exists(MESSAGES_FILE):
    with open(MESSAGES_FILE, 'w', encoding='utf-8') as f:
        json.dump([], f)

PEERS = set()

# ---------------- Helpers ----------------

def cors_json(body, status=200):
    r = web.json_response(body, status=status)
    r.headers['Access-Control-Allow-Origin'] = '*'
    r.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    r.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return r

def append_message(record):
    try:
        with open(MESSAGES_FILE, 'r+', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except Exception:
                data = []
            data.append(record)
            f.seek(0)
            json.dump(data, f, indent=2)
            f.truncate()
    except Exception as e:
        print("Failed to append message:", e)

def split_signature(sig_hex: str):
    """
    Accept '0x'-prefixed 65-byte signature hex and return (r_bytes, s_bytes, v_int)
    """
    if not isinstance(sig_hex, str):
        raise ValueError("sig must be hex string")
    s = sig_hex[2:] if sig_hex.startswith('0x') else sig_hex
    if len(s) != 130:
        raise ValueError(f"signature length must be 65 bytes hex (130 chars), got {len(s)}")
    r_hex = s[0:64]
    s_hex = s[64:128]
    v_raw = int(s[128:130], 16)
    # normalize v to 27/28 if web3 returns 0/1
    if v_raw in (0,1):
        v = v_raw + 27
    else:
        v = v_raw
    return (bytes.fromhex(r_hex), bytes.fromhex(s_hex), v)

# ---------------- WebSocket ----------------

async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    PEERS.add(ws)
    print("New websocket connection, total peers:", len(PEERS))

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except Exception:
                    print("Invalid JSON:", msg.data)
                    continue

                mtype = data.get('type')
                if mtype == 'register':
                    await broadcast({'type': 'peer-joined', 'name': data.get('name'), 'addr': data.get('addr')})
                elif mtype == 'chat':
                    # attempt server-side recovery if sig present and web3 available
                    sig = data.get('sig')
                    recovered = None
                    if sig and w3:
                        try:
                            message_hash = data.get('hash')
                            if message_hash:
                                # message was hashed client-side (hex), recover
                                msg_enc = encode_defunct(hexstr=message_hash)
                                recovered = w3.eth.account.recover_message(msg_enc, signature=sig)
                        except Exception as e:
                            print("Recover signature failed:", e)
                            recovered = None

                    record = {
                        'from': data.get('from'),
                        'ts': data.get('ts'),
                        'text': data.get('text'),
                        'hash': data.get('hash'),
                        'sig': sig,
                        'signer': recovered,
                        'received_at': int(time.time())
                    }
                    append_message(record)

                    # broadcast to peers
                    broadcast_payload = {
                        'type': 'broadcast',
                        'room': data.get('room', 'lobby'),
                        'from': data.get('from'),
                        'ts': data.get('ts'),
                        'text': data.get('text'),
                        'hash': data.get('hash'),
                        'sig': sig,
                        'signer': recovered
                    }
                    await broadcast(broadcast_payload)
                else:
                    print("Unknown ws type:", mtype)
            elif msg.type == WSMsgType.ERROR:
                print("WebSocket error:", ws.exception())
    except Exception as exc:
        print("WebSocket handler exception:", exc)
    finally:
        try:
            PEERS.discard(ws)
            await ws.close(code=WSCloseCode.GOING_AWAY, message=b'bye')
        except Exception:
            pass
        print("Connection closed, total peers:", len(PEERS))
    return ws

async def broadcast(payload):
    text = json.dumps(payload)
    remove = []
    for p in list(PEERS):
        try:
            await p.send_str(text)
        except Exception as e:
            print("Broadcast send failed, removing peer:", e)
            remove.append(p)
    for r in remove:
        PEERS.discard(r)

# ---------------- HTTP endpoints ----------------

async def store_handler(request):
    # CORS preflight
    if request.method == 'OPTIONS':
        return cors_json({'ok': True})

    if not contract or not server_account:
        return cors_json({'error': 'on-chain not configured (SERVER_PRIVATE_KEY or contract missing)'}, status=400)

    try:
        body = await request.json()
    except Exception:
        return cors_json({'error': 'invalid json'}, status=400)

    h = body.get('hash')
    sig = body.get('sig')
    sender = body.get('sender')

    if not h:
        return cors_json({'error': 'missing hash'}, status=400)

    hexstr = h[2:] if h.startswith('0x') else h
    if len(hexstr) != 64:
        return cors_json({'error': 'hash must be 32 bytes hex (64 chars). got length ' + str(len(hexstr))}, status=400)

    try:
        # pick function depending on presence of signature
        if sig:
            try:
                r_bytes, s_bytes, v_int = split_signature(sig)
            except Exception as e:
                return cors_json({'error': 'invalid signature: ' + str(e)}, status=400)

            # call storeHashWithSig(h, v, r, s)
            fn = contract.functions.storeHashWithSig(bytes.fromhex(hexstr), v_int, r_bytes, s_bytes)
        else:
            fn = contract.functions.storeHash(bytes.fromhex(hexstr))

        # build and send tx
        nonce = w3.eth.get_transaction_count(server_account.address)
        tx = fn.build_transaction({
            'chainId': w3.eth.chain_id,
            'gas': 300000,
            'gasPrice': w3.toWei('1', 'gwei'),
            'nonce': nonce
        })
        signed = w3.eth.account.sign_transaction(tx, private_key=SERVER_PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        # optional: if sig was provided and we want to verify on-chain entry we can read event
        return cors_json({'txHash': tx_hash.hex(), 'blockNumber': receipt.blockNumber})
    except Exception as e:
        print("store_handler exception:", e)
        return cors_json({'error': str(e)}, status=500)

async def history_handler(request):
    limit = int(request.query.get('limit', '200'))
    try:
        with open(MESSAGES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        data = []
    return cors_json({'messages': data[-limit:]})

# static file serving (index.html in cwd)
async def index(request):
    p = os.path.join(os.getcwd(), 'index.html')
    if os.path.exists(p):
        return web.FileResponse(path=p)
    return web.Response(status=404, text='index.html not found')

async def static_handler(request):
    fname = request.match_info.get('filename')
    pathf = os.path.join(os.getcwd(), fname)
    if os.path.exists(pathf):
        return web.FileResponse(path=pathf)
    return web.Response(status=404, text='Not found')

# --------------- App setup ---------------
app = web.Application()
app.router.add_get('/', index)
app.router.add_get('/index.html', index)
app.router.add_get(WS_PATH, websocket_handler)
app.router.add_route('OPTIONS', '/store', store_handler)
app.router.add_post('/store', store_handler)
app.router.add_get('/history', history_handler)
app.router.add_get('/{filename}', static_handler)

if __name__ == '__main__':
    print(f"Starting server on http://{HTTP_HOST}:{HTTP_PORT} (serving index.html from cwd)")
    web.run_app(app, host=HTTP_HOST, port=HTTP_PORT)
