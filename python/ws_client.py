# ws_client.py - aiohttp-based CLI WebSocket client (Python 3.12 compatible, UTF-8 encoding)
import asyncio
import json, time, hashlib, os
from aiohttp import ClientSession, ClientWebSocketResponse

REMOTE_WS = os.environ.get('WS_URL', 'http://localhost:9002/ws')  # aiohttp expects http url for ws
ADDR = os.environ.get('ADDR', '0xCLIaddr')

async def run():
    async with ClientSession() as session:
        async with session.ws_connect(REMOTE_WS) as ws:  # type: ClientWebSocketResponse
            # register
            await ws.send_str(json.dumps({'type':'register','name':'cli','addr':ADDR}))
            print("Connected. Type messages.")
            loop = asyncio.get_running_loop()
            while True:
                msg = await loop.run_in_executor(None, input, '> ')
                if not msg:
                    continue
                ts = int(time.time())
                digest = hashlib.sha256((msg + str(ts)).encode()).hexdigest()
                payload = {
                    'type':'chat',
                    'room':'lobby',
                    'from': ADDR,
                    'ts': ts,
                    'text': msg,
                    'hash': '0x' + digest
                }
                await ws.send_str(json.dumps(payload))

if __name__ == '__main__':
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nClient exited")
