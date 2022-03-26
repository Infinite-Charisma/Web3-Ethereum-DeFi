"""Transaction broadcasting and monitoring."""

import logging
import time
from typing import List, Dict, Set
import datetime

from eth_account.datastructures import SignedTransaction
from hexbytes import HexBytes
from web3 import Web3
from web3.exceptions import TransactionNotFound


logger = logging.getLogger(__name__)


class ConfirmationTimedOut(Exception):
    """We exceeded the transaction confirmation timeout."""


def wait_transactions_to_complete(
        web3: Web3,
        txs: List[HexBytes],
        confirmation_block_count: int = 0,
        max_timeout=datetime.timedelta(minutes=5),
        poll_delay=datetime.timedelta(seconds=1)) -> Dict[HexBytes, dict]:
    """Watch multiple transactions executed at parallel.

    Use simple poll loop to wait all transactions to complete.

    Example:

    .. code-block:: python

        tx_hash1 = web3.eth.send_raw_transaction(signed1.rawTransaction)
        tx_hash2 = web3.eth.send_raw_transaction(signed2.rawTransaction)

        complete = wait_transactions_to_complete(web3, [tx_hash1, tx_hash2])

        # Check both transaction succeeded
        for receipt in complete.values():
            assert receipt.status == 1  # tx success

    :param txs:
        List of transaction hashes
    :param confirmation_block_count:
        How many blocks wait for the transaction receipt to settle.
        Set to zero to return as soon as we see the first transaction receipt.
    :return:
        Map of transaction hashes -> receipt
    """

    assert isinstance(poll_delay, datetime.timedelta)
    assert isinstance(max_timeout, datetime.timedelta)
    assert isinstance(confirmation_block_count, int)

    if web3.eth.chain_id == 61:
        assert confirmation_block_count == 0, "Ethereum Tester chain does not progress itself, so we cannot wait"

    logger.info("Waiting %d transactions to confirm in %d blocks", len(txs), confirmation_block_count)

    started_at = datetime.datetime.utcnow()

    receipts_received = {}

    unconfirmed_txs: Set[HexBytes] = {HexBytes(tx) for tx in txs}

    while len(unconfirmed_txs) > 0:

        # Transaction hashes that receive confirmation on this round
        confirmation_received = set()

        for tx_hash in unconfirmed_txs:
            try:
                receipt = web3.eth.get_transaction_receipt(tx_hash)
            except TransactionNotFound as e:
                # BNB Chain get does this instead of returning None
                logger.debug("Transaction not found yet: %s", e)
                receipt = None

            if receipt:
                tx_confirmations = web3.eth.block_number - receipt.blockNumber
                if tx_confirmations >= confirmation_block_count:
                    logger.debug("Confirmed tx %s with %d confirmations", tx_hash.hex(), tx_confirmations)
                    confirmation_received.add(tx_hash)
                    receipts_received[tx_hash] = receipt
                else:
                    logger.debug("Still waiting more confirmations. Tx %s with %d confirmations, %d needed", tx_hash.hex(), tx_confirmations, confirmation_block_count)

        # Remove confirmed txs from the working set
        unconfirmed_txs -= confirmation_received

        if unconfirmed_txs:
            time.sleep(poll_delay.total_seconds())

            if datetime.datetime.utcnow() > started_at + max_timeout:
                for tx_hash in unconfirmed_txs:
                    tx_data = web3.eth.get_transaction(tx_hash)
                    logger.error("Data for transaction %s was %s", tx_hash.hex(), tx_data)
                raise ConfirmationTimedOut(f"Transaction confirmation failed. Started: {started_at}, timed out after {max_timeout}. Still unconfirmed: {unconfirmed_txs}")

    return receipts_received


def broadcast_and_wait_transactions_to_complete(
        web3: Web3,
        txs: List[SignedTransaction],
        confirm_ok=True,
        confirmation_block_count: int = 0,
        max_timeout=datetime.timedelta(minutes=5),
        poll_delay=datetime.timedelta(seconds=1)) -> Dict[HexBytes, dict]:
    """Broadcast and wait a bunch of signed transactions to confirm.

    :param web3: Web3
    :param txs: List of Signed transactions
    :param confirm_ok: Raise an error if any of the transaction reverts
    :param max_timeout: How long we wait until we give up waiting transactions to complete
    :param poll_delay: Poll timeout between the tx check loops
    :param confirmation_block_count:
        How many blocks wait for the transaction receipt to settle.
        Set to zero to return as soon as we see the first transaction receipt.
    :return: Map transaction hash -> receipt
    """

    # Broadcast transactions to the mempool
    hashes = []
    for tx in txs:
        assert isinstance(tx, SignedTransaction), f"Got {tx}"
        hash = web3.eth.send_raw_transaction(tx.rawTransaction)
        hashes.append(hash)

    # Wait transactions to confirm
    receipts = wait_transactions_to_complete(web3, hashes, confirmation_block_count, max_timeout, poll_delay)

    if confirm_ok:
        for tx_hash, receipt in receipts.items():
            if receipt.status != 1:
                raise RuntimeError(f"Transaction {tx_hash} failed {receipt}")

    return receipts

