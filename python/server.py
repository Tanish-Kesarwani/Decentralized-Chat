# --- Python 3.12 compatibility shim for parsimonious (adds inspect.getargspec) ---
import inspect
if not hasattr(inspect, "getargspec"):
    from collections import namedtuple
    ArgSpec = namedtuple("ArgSpec", "args varargs keywords defaults")
    def getargspec(func):
        return ArgSpec(*inspect.getfullargspec(func)[:4])
    inspect.getargspec = getargspec
# -------------------------------------------------------------------------
# server.py (updated for signature storing + history)
import asyncio, json, os, time
from aiohttp import web, WSMsgType
from web3 import Web3
from eth_account.messages import encode_defunct

WS_PATH = '/ws'
HTTP_HOST = '0.0.0.0'
HTTP_PORT = 9002

CONTRACT_INFO_PATH = 'contract_info.json'
RPC_URL = os.environ.get('RPC_URL', 'http://127.0.0.1:8545')
SERVER_PRIVATE_KEY = os.environ.get('SERVER_PRIVATE_KEY')  # optional

MESSAGES_FILE = 'messages.json'  # persistent store for chat messages

# load contract info if present
contract_info = {}
if os.path.exists(CONTRACT_INFO_PATH):
    with open(CONTRACT_INFO_PATH, 'r') as f:
        contract_info = json.load(f)
CONTRACT_ADDRESS = contract_info.get('address')
CONTRACT_ABI = contract_info.get('abi')

w3 = None
contract = None
server_account = None
if CONTRACT_ADDRESS and CONTRACT_ABI and SERVER_PRIVATE_KEY:
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)
    acct = w3.eth.account.from_key(SERVER_PRIVATE_KEY)
    server_account = acct
    print("Server will submit txs using address:", acct.address)
else:
    print("On-chain writing not configured (set SERVER_PRIVATE_KEY and ensure contract_info.json exists to enable).")

PEERS = set()

# ensure messages.json exists
if not os.path.exists(MESSAGES_FILE):
    with open(MESSAGES_FILE, 'w') as f:
        json.dump([], f)

def append_message_record(record):
    # append to messages.json (simple file append)
    try:
        with open(MESSAGES_FILE, 'r+') as f:
            data = json.load(f)
            data.append(record)
            f.seek(0)
            json.dump(data, f, indent=2)
            f.truncate()
    except Exception as e:
        print("Failed to append message record:", e)

def cors_response(body, status=200):
    resp = web.json_response(body, status=status)
    resp.headers['Access-Control-Allow-Origin'] = '*' 
    resp.headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return resp

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
                    # attempt to recover signer if signature present
                    sig = data.get('sig')
                    recovered = None
                    if sig:
                        try:
                            # sig is hex string like 0x...
                            hexmsg = data.get('hash')  # we trust client-supplied hash for recovery
                            # encode and recover (eth_account expects prefixed message for personal_sign)
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
                    # persist
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
    finally:
        PEERS.discard(ws)
        print("Connection closed, total peers:", len(PEERS))
    return ws

async def broadcast(payload):
    text = json.dumps(payload)
    to_remove = []
    for ws in list(PEERS):
        try:
            await ws.send_str(text)
        except Exception as e:
            print("Failed send to peer, removing:", e)
            to_remove.append(ws)
    for r in to_remove:
        PEERS.discard(r)

# endpoints

# store hash on-chain endpoint (same as before)
async def store_hash_handler(request):
    if request.method == 'OPTIONS':
        return cors_response({'ok': True})
    if not contract or not server_account:
        return cors_response({'error': 'on-chain not configured'}, status=400)
    try:
        body = await request.json()
    except Exception:
        return cors_response({'error': 'invalid json'}, status=400)
    h = body.get('hash')
    if not h:
        return cors_response({'error': 'missing hash'}, status=400)
    hexstr = h[2:] if h.startswith('0x') else h
    if len(hexstr) != 64:
        return cors_response({'error': 'hash must be 32 bytes hex (64 chars)'}, status=400)
    try:
        tx = contract.functions.storeHash(bytes.fromhex(hexstr)).build_transaction({
            'chainId': w3.eth.chain_id,
            'gas': 200000,
            'gasPrice': w3.toWei('1', 'gwei'),
            'nonce': w3.eth.get_transaction_count(server_account.address)
        })
        signed = w3.eth.account.sign_transaction(tx, SERVER_PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        return cors_response({'txHash': tx_hash.hex(), 'blockNumber': receipt.blockNumber})
    except Exception as e:
        return cors_response({'error': str(e)}, status=500)

# history endpoint
async def history_handler(request):
    limit = int(request.query.get('limit', '100'))
    try:
        with open(MESSAGES_FILE, 'r') as f:
            data = json.load(f)
    except Exception:
        data = []
    return cors_response({'messages': data[-limit:]})

# serve UI index.html
async def index(request):
    return web.FileResponse(path=os.path.join(os.getcwd(), 'index.html'))

# static file handler
async def static_file(request):
    filename = request.match_info.get('filename')
    file_path = os.path.join(os.getcwd(), filename)
    if os.path.exists(file_path):
        return web.FileResponse(path=file_path)
    return web.Response(status=404, text='Not found')

app = web.Application()
app.router.add_get('/', index)
app.router.add_get('/index.html', index)
app.router.add_get(WS_PATH, websocket_handler)
app.router.add_route('OPTIONS', '/store', store_hash_handler)
app.router.add_post('/store', store_hash_handler)
app.router.add_get('/history', history_handler)
app.router.add_get('/{filename}', static_file)

if __name__ == '__main__':
    print(f"Starting server on http://{HTTP_HOST}:{HTTP_PORT} (serving index.html from cwd)")
    web.run_app(app, host=HTTP_HOST, port=HTTP_PORT)

