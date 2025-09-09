# server.py
# Complete server for Decentralized Chat (Phase 6 ready)
# - WebSocket broadcast
# - static file serving (index.html)
# - CORS-enabled /store that can call storeHash or storeHashWithSig on-chain
# - message persistence and /history endpoint
# - Python 3.12 shim to support parsimonious used by web3 deps

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
import asyncio
from aiohttp import web, WSMsgType, WSCloseCode
from web3 import Web3
from eth_account.messages import encode_defunct

# ----------------- Configuration -----------------
WS_PATH = '/ws'
HTTP_HOST = '0.0.0.0'
HTTP_PORT = int(os.environ.get('HTTP_PORT', '9002'))

CONTRACT_INFO_PATH = 'contract_info.json'   # written by deploy.js
RPC_URL = os.environ.get('RPC_URL', 'http://127.0.0.1:8545')
SERVER_PRIVATE_KEY = os.environ.get('SERVER_PRIVATE_KEY')  # server pays gas if set

MESSAGES_FILE = 'messages.json'
# --------------------------------------------------

# Load contract info (address + abi)
contract_info = {}
if os.path.exists(CONTRACT_INFO_PATH):
    try:
        with open(CONTRACT_INFO_PATH, 'r') as f:
            contract_info = json.load(f)
    except Exception as e:
        print("Failed to read contract_info.json:", e)

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
    print("On-chain writing not configured (set SERVER_PRIVATE_KEY and ensure contract_info.json exists to enable).")

# Ensure messages.json exists
if not os.path.exists(MESSAGES_FILE):
    with open(MESSAGES_FILE, 'w') as f:
        json.dump([], f)

PEERS = set()

# ----------------- Helpers -----------------

def cors_response(body, status=200):
    """Return a JSON response with permissive CORS headers for demo."""
    resp = web.json_response(body, status=status)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return resp

def append_message_record(record):
    """Append message to messages.json safely."""
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
        print("Failed to append message record:", e)

def split_signature(sig_hex: str):
    """
    Convert a 65-byte signature hex string (0x...) to (r_bytes, s_bytes, v_int).
    Accepts v as 0/1 or 27/28, returns v as 27/28 for EVM.
    """
    if not isinstance(sig_hex, str):
        raise ValueError("signature must be hex string")
    s = sig_hex[2:] if sig_hex.startswith('0x') else sig_hex
    if len(s) != 130:
        raise ValueError("signature must be 65 bytes hex (130 hex chars), got length {}".format(len(s)))
    r = bytes.fromhex(s[0:64])
    s_ = bytes.fromhex(s[64:128])
    v_raw = int(s[128:130], 16)
    # normalize v to 27/28
    if v_raw in (0, 1):
        v = v_raw + 27
    else:
        v = v_raw
    return (r, s_, v)

# ----------------- WebSocket handlers -----------------

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
                    print("Invalid JSON received:", msg.data)
                    continue

                mtype = data.get('type')
                if mtype == 'register':
                    payload = {'type': 'peer-joined', 'addr': data.get('addr'), 'name': data.get('name')}
                    await broadcast(payload)
                elif mtype == 'chat':
                    # recover signer if signature present (best-effort)
                    sig = data.get('sig')
                    recovered = None
                    if sig and w3:
                        try:
                            hexmsg = data.get('hash')
                            if not hexmsg:
                                raise ValueError("no hash to recover from")
                            message = encode_defunct(hexstr=hexmsg)
                            recovered = w3.eth.account.recover_message(message, signature=sig)
                        except Exception as e:
                            print("Signature recovery failed:", e)
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
                    append_message_record(record)

                    payload = {
                        'type': 'broadcast',
                        'room': data.get('room', 'lobby'),
                        'from': data.get('from'),
                        'ts': data.get('ts'),
                        'text': data.get('text'),
                        'hash': data.get('hash'),
                        'sig': sig,
                        'signer': recovered
                    }
                    await broadcast(payload)
                else:
                    print("Unknown message type:", mtype)
            elif msg.type == WSMsgType.ERROR:
                print('WebSocket closed with exception:', ws.exception())
    except Exception as e:
        print("WebSocket handler exception:", e)
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
    for ws in list(PEERS):
        try:
            await ws.send_str(text)
        except Exception as e:
            print("Failed send to peer, removing:", e)
            remove.append(ws)
    for r in remove:
        PEERS.discard(r)

# ----------------- HTTP endpoints -----------------

async def store_hash_handler(request):
    """
    POST /store
    Body JSON: { hash: "0x...", sig?: "0x...", sender?: "0x..." }
    If sig present -> call storeHashWithSig(hash, v, r, s)
    Else -> call storeHash(hash)
    """
    if request.method == 'OPTIONS':
        return cors_response({'ok': True})

    if not contract or not server_account:
        return cors_response({'error': 'on-chain not configured'}, status=400)

    try:
        body = await request.json()
    except Exception:
        return cors_response({'error': 'invalid json'}, status=400)

    h = body.get('hash')
    sig = body.get('sig')

    if not h:
        return cors_response({'error': 'missing hash'}, status=400)

    hexstr = h[2:] if h.startswith('0x') else h
    if len(hexstr) != 64:
        return cors_response({'error': 'hash must be 32 bytes hex (64 chars)'}, status=400)

    try:
        # Build tx depending on presence of signature
        if sig:
            try:
                r_bytes, s_bytes, v = split_signature(sig)
            except Exception as e:
                return cors_response({'error': 'invalid signature format: ' + str(e)}, status=400)

            # Use raw bytes for r and s when calling contract function
            tx_fn = contract.functions.storeHashWithSig(bytes.fromhex(hexstr), v, r_bytes, s_bytes)
        else:
            tx_fn = contract.functions.storeHash(bytes.fromhex(hexstr))

        tx = tx_fn.build_transaction({
            'chainId': w3.eth.chain_id,
            'gas': 300000,
            'gasPrice': w3.toWei('1', 'gwei'),
            'nonce': w3.eth.get_transaction_count(server_account.address)
        })

        signed = w3.eth.account.sign_transaction(tx, SERVER_PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        return cors_response({'txHash': tx_hash.hex(), 'blockNumber': receipt.blockNumber})
    except Exception as e:
        # Return error info for debugging
        print("store_hash_handler error:", e)
        return cors_response({'error': str(e)}, status=500)

async def history_handler(request):
    limit = int(request.query.get('limit', '100'))
    try:
        with open(MESSAGES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        data = []
    return cors_response({'messages': data[-limit:]})

# serve index.html and static files from cwd (same origin)
async def index(request):
    p = os.path.join(os.getcwd(), 'index.html')
    if os.path.exists(p):
        return web.FileResponse(path=p)
    return web.Response(status=404, text='index.html not found')

async def static_file(request):
    filename = request.match_info.get('filename')
    file_path = os.path.join(os.getcwd(), filename)
    if os.path.exists(file_path):
        return web.FileResponse(path=file_path)
    return web.Response(status=404, text='Not found')

# ----------------- App setup -----------------

app = web.Application()
app.router.add_get('/', index)
app.router.add_get('/index.html', index)
app.router.add_get(WS_PATH, websocket_handler)
app.router.add_route('OPTIONS', '/store', store_hash_handler)
app.router.add_post('/store', store_hash_handler)
app.router.add_get('/history', history_handler)
app.router.add_get('/{filename}', static_file)

if __name__ == '__main__':
    print(f"Starting server on http://{HTTP_HOST if 'HTTP_HOST' in globals() else '0.0.0.0'}:{HTTP_PORT} (serving index.html from cwd)")
    web.run_app(app, host=HTTP_HOST if 'HTTP_HOST' in globals() else '0.0.0.0', port=HTTP_PORT)
