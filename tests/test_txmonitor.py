"""Transaction monitoring tests."""
import secrets

import pytest
from eth_account import Account
from eth_account.signers.local import LocalAccount

from eth_typing import HexAddress
from hexbytes import HexBytes
from web3 import Web3, EthereumTesterProvider
from web3._utils.transactions import fill_nonce

from smart_contracts_for_testing.gas import estimate_gas_fees, GasPriceMethod, apply_gas
from smart_contracts_for_testing.token import create_token
from smart_contracts_for_testing.txmonitor import wait_transactions_to_complete, \
    broadcast_and_wait_transactions_to_complete


@pytest.fixture
def tester_provider():
    # https://web3py.readthedocs.io/en/stable/examples.html#contract-unit-tests-in-python
    return EthereumTesterProvider()


@pytest.fixture
def eth_tester(tester_provider):
    # https://web3py.readthedocs.io/en/stable/examples.html#contract-unit-tests-in-python
    return tester_provider.ethereum_tester


@pytest.fixture
def web3(tester_provider):
    """Set up a local unit testing blockchain."""
    # https://web3py.readthedocs.io/en/stable/examples.html#contract-unit-tests-in-python
    return Web3(tester_provider)


@pytest.fixture()
def deployer(web3) -> str:
    """Deploy account.

    Do some account allocation for tests.
    """
    return web3.eth.accounts[0]


@pytest.fixture()
def hot_wallet_private_key(web3) -> HexBytes:
    """Generate a private key"""
    return HexBytes(secrets.token_bytes(32))


@pytest.fixture()
def hot_wallet(web3, hot_wallet_private_key) -> LocalAccount:
    """User account.

    Do some account allocation for tests.
    """
    return Account.from_key(hot_wallet_private_key)


def test_wait_txs_parallel(web3: Web3, eth_tester, deployer: HexAddress, hot_wallet: LocalAccount):
    """Wait multiple transactions to complete in parallel."""

    gas_fees = estimate_gas_fees(web3)

    token = create_token(web3, deployer, "Cow token", "COWS", 100_000 * 10**18)

    # Drop some ETH and token to the hot wallet
    web3.eth.send_transaction({"from": deployer, "to": hot_wallet.address, "value": 1 * 10**18})
    token.functions.transfer(hot_wallet.address, 50_000 * 10**18).transact({"from": deployer})

    nonce = web3.eth.get_transaction_count(hot_wallet.address)

    # Create a raw transaction
    # Move 10 tokens from deployer to user1
    # https://web3py.readthedocs.io/en/stable/contracts.html?highlight=buildTransaction#web3.contract.ContractFunction.buildTransaction
    tx1 = token.functions.transfer(hot_wallet.address, 10 * 10**18).buildTransaction({
        "from": hot_wallet.address,
        'chainId': web3.eth.chain_id,
        "gas": 150_000,  # 150k gas should be more than enough for ERC20.transfer(),
        "nonce": nonce,
    })

    tx2 = token.functions.transfer(hot_wallet.address, 10 * 10**18).buildTransaction({
        "from": hot_wallet.address,
        'chainId': web3.eth.chain_id,
        "gas": 150_000,  # 150k gas should be more than enough for ERC20.transfer()
        "nonce": nonce + 1,
    })

    apply_gas(tx1, gas_fees)
    apply_gas(tx2, gas_fees)

    signed1 = hot_wallet.sign_transaction(tx1)
    signed2 = hot_wallet.sign_transaction(tx2)

    tx_hash1 = web3.eth.send_raw_transaction(signed1.rawTransaction)
    tx_hash2 = web3.eth.send_raw_transaction(signed2.rawTransaction)

    complete = wait_transactions_to_complete(web3, [tx_hash1, tx_hash2])

    # Check both transaction succeeded
    for receipt in complete.values():
        assert receipt.status == 1  # tx success


def test_broadcast_and_wait(web3: Web3, eth_tester, deployer: HexAddress, hot_wallet: LocalAccount):
    """Broadcast and multiple transactions to complete in parallel."""

    gas_fees = estimate_gas_fees(web3)

    token = create_token(web3, deployer, "Cow token", "COWS", 100_000 * 10**18)

    # Drop some ETH and token to the hot wallet
    web3.eth.send_transaction({"from": deployer, "to": hot_wallet.address, "value": 1 * 10**18})
    token.functions.transfer(hot_wallet.address, 50_000 * 10**18).transact({"from": deployer})

    nonce = web3.eth.get_transaction_count(hot_wallet.address)

    # Create a raw transaction
    # Move 10 tokens from deployer to user1
    # https://web3py.readthedocs.io/en/stable/contracts.html?highlight=buildTransaction#web3.contract.ContractFunction.buildTransaction
    tx1 = token.functions.transfer(hot_wallet.address, 10 * 10**18).buildTransaction({
        "from": hot_wallet.address,
        'chainId': web3.eth.chain_id,
        "gas": 150_000,  # 150k gas should be more than enough for ERC20.transfer(),
        "nonce": nonce,
    })

    tx2 = token.functions.transfer(hot_wallet.address, 10 * 10**18).buildTransaction({
        "from": hot_wallet.address,
        'chainId': web3.eth.chain_id,
        "gas": 150_000,  # 150k gas should be more than enough for ERC20.transfer()
        "nonce": nonce + 1,
    })

    apply_gas(tx1, gas_fees)
    apply_gas(tx2, gas_fees)

    signed1 = hot_wallet.sign_transaction(tx1)
    signed2 = hot_wallet.sign_transaction(tx2)

    complete = broadcast_and_wait_transactions_to_complete(web3, [signed1, signed2])

    # Check both transaction succeeded
    for receipt in complete.values():
        assert receipt.status == 1  # tx success


