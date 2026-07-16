// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title InjFaucet — one-time 1 INJ claim per wallet (Injective EVM testnet)
/// @notice Owner funds the contract and calls claimFor for gasless claims via Arena64 API.
contract InjFaucet {
    uint256 public constant CLAIM_AMOUNT = 1 ether; // 1 INJ

    address public owner;
    mapping(address => bool) public claimed;

    event Claimed(address indexed to, uint256 amount);
    event Funded(address indexed from, uint256 amount);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    error NotOwner();
    error AlreadyClaimed();
    error InsufficientFaucetBalance();
    error ZeroAddress();
    error TransferFailed();

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    constructor() {
        owner = msg.sender;
        emit OwnershipTransferred(address(0), msg.sender);
    }

    receive() external payable {
        emit Funded(msg.sender, msg.value);
    }

    function fund() external payable {
        emit Funded(msg.sender, msg.value);
    }

    function hasClaimed(address account) external view returns (bool) {
        return claimed[account];
    }

    function faucetBalance() external view returns (uint256) {
        return address(this).balance;
    }

    /// @notice Gasless path: Arena64 API (owner) drips 1 INJ to `to`. One claim forever.
    function claimFor(address to) external onlyOwner {
        if (to == address(0)) revert ZeroAddress();
        if (claimed[to]) revert AlreadyClaimed();
        if (address(this).balance < CLAIM_AMOUNT) revert InsufficientFaucetBalance();

        claimed[to] = true;
        (bool ok, ) = to.call{value: CLAIM_AMOUNT}("");
        if (!ok) revert TransferFailed();
        emit Claimed(to, CLAIM_AMOUNT);
    }

    /// @notice Self-claim if the wallet already has gas. Same once-per-wallet rule.
    function claim() external {
        if (claimed[msg.sender]) revert AlreadyClaimed();
        if (address(this).balance < CLAIM_AMOUNT) revert InsufficientFaucetBalance();

        claimed[msg.sender] = true;
        (bool ok, ) = msg.sender.call{value: CLAIM_AMOUNT}("");
        if (!ok) revert TransferFailed();
        emit Claimed(msg.sender, CLAIM_AMOUNT);
    }

    function transferOwnership(address newOwner) external onlyOwner {
        if (newOwner == address(0)) revert ZeroAddress();
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }

    /// @notice Emergency drain remaining INJ back to owner.
    function withdraw(uint256 amount) external onlyOwner {
        (bool ok, ) = owner.call{value: amount}("");
        if (!ok) revert TransferFailed();
    }
}
