// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

contract MessageRegistry {
    struct Entry {
        address signer; // recovered signer (address(0) if none)
        bytes32 hash;   // message hash (bytes32)
        uint256 ts;     // block timestamp when stored
    }

    Entry[] public entries;

    event HashStored(address indexed signer, bytes32 hash, uint256 indexed idx);

    // store a raw hash (server pays gas, no signer verification)
    function storeHash(bytes32 h) external returns (uint256) {
        entries.push(Entry(address(0), h, block.timestamp));
        uint256 idx = entries.length - 1;
        emit HashStored(address(0), h, idx);
        return idx;
    }

    // store a hash with an ECDSA signature (v,r,s); recover signer and save
    function storeHashWithSig(bytes32 h, uint8 v, bytes32 r, bytes32 s) external returns (uint256) {
        // recreate the Ethereum signed message hash that personal_sign uses:
        bytes32 prefixed = keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32", h));
        address signer = ecrecover(prefixed, v, r, s);
        entries.push(Entry(signer, h, block.timestamp));
        uint256 idx = entries.length - 1;
        emit HashStored(signer, h, idx);
        return idx;
    }

    function entriesCount() external view returns (uint256) {
        return entries.length;
    }

    function getEntry(uint256 i) external view returns (address signer, bytes32 hash, uint256 ts) {
        Entry memory e = entries[i];
        return (e.signer, e.hash, e.ts);
    }

    // helper to verify a signature off-chain or on-chain if needed
    function recoverSigner(bytes32 h, uint8 v, bytes32 r, bytes32 s) external pure returns (address) {
        bytes32 prefixed = keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32", h));
        return ecrecover(prefixed, v, r, s);
    }
}
