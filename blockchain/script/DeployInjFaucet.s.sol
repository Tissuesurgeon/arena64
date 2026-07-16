// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {InjFaucet} from "../src/InjFaucet.sol";

/// @dev Deploy with:
///   forge create src/InjFaucet.sol:InjFaucet \
///     --rpc-url $INJECTIVE_RPC_URL \
///     --private-key $INJ_KEY_EVM \
///     --broadcast
/// Or: forge script script/DeployInjFaucet.s.sol:DeployInjFaucet --rpc-url ... --broadcast
contract DeployInjFaucet {
    function run() external returns (InjFaucet faucet) {
        // Lightweight script without forge-std Script (no git dep required).
        // Prefer `forge create` in README; this file documents the intended entrypoint.
        faucet = new InjFaucet();
    }
}
