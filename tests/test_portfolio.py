"""Mock token deployment."""
from decimal import Decimal

import pytest

from eth_tester.exceptions import TransactionFailed
from web3 import Web3, EthereumTesterProvider
from web3.contract import Contract

from eth_hentai.portfolio import fetch_erc20_balances, fetch_erc20_balances_decimal
from eth_hentai.token import create_token


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
def user_1(web3) -> str:
    """User account.

    Do some account allocation for tests.
    """
    return web3.eth.accounts[1]


@pytest.fixture()
def usdc(web3, deployer) -> Contract:
    """Mock USDC token.

    Note that this token has 18 decimals instead of 6 of real USDC.
    """
    token = create_token(web3, deployer, "USD Coin", "USDC", 10_000_000 * 10**18, 6)
    return token


@pytest.fixture()
def aave(web3, deployer) -> Contract:
    """Mock Aave token."""
    token = create_token(web3, deployer, "Aave", "AAVE", 10_000_000 * 10**18)
    return token


def test_portfolio_current(web3: Web3, deployer: str, user_1: str, usdc: Contract, aave: Contract):
    """Analyse current holdings of an address."""

    # Load up the user with some tokens
    usdc.functions.transfer(user_1, 500).transact({"from": deployer})
    aave.functions.transfer(user_1, 200).transact({"from": deployer})
    balances = fetch_erc20_balances(web3, user_1)
    assert balances[usdc.address] == 500
    assert balances[aave.address] == 200


def test_portfolio_past(web3: Web3, deployer: str, user_1: str, usdc: Contract, aave: Contract):
    """Analyse past holdings of an address."""

    # Load up the user with some tokens
    usdc.functions.transfer(user_1, 500).transact({"from": deployer})
    aave.functions.transfer(user_1, 200).transact({"from": deployer})

    threshold_block = web3.eth.blockNumber

    # Top up AAVE which won't show up in the analysis
    aave.functions.transfer(user_1, 333).transact({"from": deployer})

    balances = fetch_erc20_balances(web3, user_1, last_block_num=threshold_block)
    assert balances[usdc.address] == 500
    assert balances[aave.address] == 200

    balances = fetch_erc20_balances(web3, user_1)
    assert balances[aave.address] == 533


def test_portfolio_decimals(web3: Web3, deployer: str, user_1: str, usdc: Contract, aave: Contract):
    """Analyse current holdings with human-readable decimal balances."""

    # Load up the user with some tokens
    usdc.functions.transfer(user_1, 500).transact({"from": deployer})
    aave.functions.transfer(user_1, 200).transact({"from": deployer})
    balances = fetch_erc20_balances_decimal(web3, user_1)
    assert balances[usdc.address].value == Decimal('0.0005')
    assert balances[usdc.address].decimals == 6
    assert balances[aave.address].value == Decimal(200) / Decimal(10**18)
    assert balances[aave.address].decimals == 18
