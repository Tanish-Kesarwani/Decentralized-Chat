# 🕸️ Decentralized Chat  
**WebSocket + Blockchain Anchoring + MetaMask Signatures**

A hybrid **decentralized chat application** that combines **real-time messaging** (via WebSockets) with **tamper-proof anchoring** of messages on the Ethereum blockchain.  
This project demonstrates how **off-chain scalability** (fast messaging) can be combined with **on-chain verifiability** (blockchain storage + digital signatures).

---

## ✨ Features

- ⚡ **Real-time Chat** — powered by WebSockets (`aiohttp` + Python server)  
- ⛓️ **On-chain Anchoring** — message hashes (SHA-256) stored on Ethereum  
- 🔐 **MetaMask Integration** — sign messages with Ethereum wallet  
- ✅ **Signature Verification** — Solidity contract ensures authenticity  
- 🌐 **Browser UI** — lightweight `index.html` (no heavy frameworks)  
- 💻 **Cross-Client Support** — chat via:
  - Python CLI client (`ws_client.py`)  
  - Browser client (with/without MetaMask)  

---

## 📂 Project Structure

```text
decentralized_chat/
├── python/                # Python server + clients
│   ├── server.py          # WebSocket + REST API server
│   ├── ws_client.py       # CLI WebSocket chat client
│   ├── peer_server.py     # (old P2P prototype)
│   ├── peer_client.py     # (old P2P prototype)
│   ├── check_entry.py     # Inspect contract entries
│   ├── contract_info.json # ABI + deployed contract address
│   └── requirements.txt   # Python dependencies
│
├── solidity/              # Hardhat smart contracts
│   ├── contracts/
│   │   └── MessageRegistry.sol
│   ├── scripts/deploy.js
│   ├── hardhat.config.js
│   └── package.json
│
├── index.html             # Web UI
└── README.md

---


---

## ⚙️ Setup Instructions

### 1️⃣ Clone Repo
```bash
git clone https://github.com/<your-username>/Decentralized-Chat.git
cd Decentralized-Chat
2️⃣ Install Dependencies

🔹 Python (backend + CLI client)

cd python
python -m venv venv
# Windows
.\venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt

🔹 Node.js (Solidity contracts)

cd solidity
npm install

3️⃣ Run Local Blockchain (Hardhat)
cd solidity
npx hardhat node

4️⃣ Deploy Smart Contract
cd solidity
npx hardhat run --network localhost scripts/deploy.js


👉 This writes the deployed contract’s address + ABI to:
python/contract_info.json

5️⃣ Start Python Server
cd python
.\venv\Scripts\activate

# Example: Windows PowerShell
$env:SERVER_PRIVATE_KEY="0x<your-private-key>"
$env:RPC_URL="http://127.0.0.1:8545"

python server.py


🌐 Server runs at: http://localhost:9002

6️⃣ Open Web UI

Open python/index.html directly, or

Visit http://localhost:9002 if served by Python server

✔️ Enter your username + address
✔️ Tick “Use MetaMask to sign” for wallet-based signatures

8️⃣ Verify On-Chain Entries
cd python
python check_entry.py

🧩 Smart Contract: MessageRegistry.sol
| Function                                                     | Description                                                 |
| ------------------------------------------------------------ | ----------------------------------------------------------- |
| `storeHash(bytes32 h)`                                       | Stores a message hash (server pays gas).                    |
| `storeHashWithSig(bytes32 h, uint8 v, bytes32 r, bytes32 s)` | Stores a signed hash and recovers signer using `ecrecover`. |
| `getEntry(uint256 i)`                                        | Returns `(signer, hash, timestamp)`.                        |
| `entriesCount()`                                             | Returns total number of stored entries.                     |

🚀 Project Status

✅ Phase 1: WebSocket server + CLI client

✅ Phase 2: Browser UI

✅ Phase 3: Client-side hashing (crypto.subtle)

✅ Phase 4: Server anchoring messages on-chain

✅ Phase 5: MetaMask signing integrated

✅ Phase 6: On-chain signature verification


---


