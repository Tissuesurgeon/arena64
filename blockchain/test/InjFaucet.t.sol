// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {InjFaucet} from "../src/InjFaucet.sol";

contract InjFaucetSmoke {
    function check() external {
        InjFaucet f = new InjFaucet();
        require(f.CLAIM_AMOUNT() == 1 ether, "claim amount");
        require(f.owner() == address(this), "owner");
    }
}
