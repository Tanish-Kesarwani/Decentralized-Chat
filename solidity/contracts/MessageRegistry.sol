// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

contract MessageRegistry {
    struct Entry {
        address sender;
        bytes32 hash;
        uint256 timestamp;
    }

    Entry[] public entries;

    event Registered(uint256 indexed id, address indexed sender, bytes32 hash, uint256 timestamp);

    function storeHash(bytes32 _hash) external {
        entries.push(Entry(msg.sender, _hash, block.timestamp));
        emit Registered(entries.length - 1, msg.sender, _hash, block.timestamp);
    }

    function entriesCount() external view returns (uint256) {
        return entries.length;
    }

    function getEntry(uint256 idx) external view returns (address, bytes32, uint256) {
        Entry storage e = entries[idx];
        return (e.sender, e.hash, e.timestamp);
    }
}
