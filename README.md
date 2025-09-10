# Decentralized Chat: Blockchain-Secured Messaging Platform 🚀

> A modern chat application combining real-time messaging with blockchain security - where WhatsApp meets Ethereum.

## ✨ Why This Project?
* **Security First**: Cryptographically signed and verified messages
* **Decentralized Trust**: No central authority controls message validity
* **Real-Time Communication**: WebSocket-powered instant messaging
* **Blockchain Integration**: Ethereum-based message verification

## 🎯 Core Features

### 1. Real-Time Chat
* Instant WebSocket message delivery
* Multi-user support
* Persistent message history
* Intuitive web interface

### 2. Blockchain Security
* Ethereum smart contract verification
* MetaMask integration
* On-chain message hash storage
* Immutable message records

### 3. Technical Features
* WebSocket real-time communication
* SHA-256 message hashing
* Ethereum smart contract integration
* MetaMask wallet connectivity

## 🛠️ Technical Architecture

### Frontend Layer
```plaintext
📁 python/static/
├── js/
│   ├── client.js      # WebSocket handling
│   ├── blockchain.js  # Web3 integration
│   └── ui.js          # User interface logic
├── css/
│   └── style.css      # Application styling
└── index.html         # Main application page
```

### Backend Layer
```plaintext
📁 python/
├── server.py          # WebSocket server
├── message_handler.py
└── blockchain_utils.py
```

### Smart Contract Layer
```plaintext
📁 solidity/contracts/
└── MessageRegistry.sol # Message verification contract
```

## 🚀 Setup Guide

### Prerequisites
* Python 3.8+
* Node.js 14+
* MetaMask browser extension
* Ethereum testnet (Goerli) access
* Web3 provider (Infura/Alchemy)

### Installation Steps

1. **Clone & Setup Environment**
```bash
git clone https://github.com/yourusername/decentralized_chat.git
cd decentralized_chat
python -m venv venv
.\venv\Scripts\activate  # Windows
```

2. **Install Dependencies**
```bash
pip install -r requirements.txt
npm install
```

3. **Configure Environment**
```bash
# Create .env file
ETHEREUM_NETWORK=goerli
WEB3_PROVIDER_URL=your_provider_url
CONTRACT_ADDRESS=deployed_contract_address
```

4. **Deploy Smart Contract**
```bash
npx hardhat compile
npx hardhat run scripts/deploy.js --network goerli
```

## 💡 Implementation Examples

### WebSocket Connection
```javascript
// filepath: python/static/js/client.js
const ws = new WebSocket('ws://localhost:8765');
ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    displayMessage(message);
};
```

### Message Signing
```javascript
// filepath: python/static/js/blockchain.js
async function signMessage(message) {
    const accounts = await ethereum.request({ method: 'eth_requestAccounts' });
    const signature = await ethereum.request({
        method: 'personal_sign',
        params: [message, accounts[0]]
    });
    return signature;
}
```

### Smart Contract Verification
```solidity
// filepath: solidity/contracts/MessageRegistry.sol
pragma solidity ^0.8.0;

contract MessageRegistry {
    mapping(bytes32 => bool) public verifiedMessages;
    
    function verifyMessage(bytes32 messageHash, bytes memory signature) public {
        address signer = recover(messageHash, signature);
        verifiedMessages[messageHash] = true;
        emit MessageVerified(messageHash, signer);
    }
}
```

## 🔍 Message Flow
1. User inputs message
2. Optional MetaMask signing
3. WebSocket transmission
4. Server broadcast
5. Blockchain verification (if signed)
6. Message display & verification status

## 🤝 Contributing

### Development Process
1. Fork repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

### Coding Standards
* Python: PEP 8
* JavaScript: ESLint (Airbnb)
* Solidity: Official style guide

## 📈 Future Roadmap
* End-to-end encryption
* Group chat functionality
* File sharing capabilities
* Multi-blockchain support
* Custom token integration

