# Copyright (C) 2025, Ionic.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

"""Defines Solana block, transaction, and wrapper data structures for indexing and processing."""
from typing import Literal

from msgspec import Struct, field

from ionic_solana_indexer.block.block_structs_base64 import (
    TransactionHeader,
    TransactionMeta,
    Instruction,
    AddressTableLookup,
)


class TransactionMessage(Struct, forbid_unknown_fields=True):
    accountKeys: list[str]
    """
    List of base-58 encoded public keys used by the transaction, including by the instructions and for signatures.
    The first message.header.numRequiredSignatures public keys must sign the transaction.

    List of `AccountKey` objects if requested with `jsonParsed` encoding.

    """

    header: TransactionHeader
    """Details the account types and signatures required by the transaction"""

    recentBlockhash: str
    """
    A base-58 encoded hash of a recent block in the ledger used to prevent transaction duplication and to give
    transactions lifetimes.

    source: https://solana.com/docs/advanced/confirmation
    Solana validators maintain a BlockhashQueue, which stores the 300 most recent blockhashes.
    Each blockhash in this queue corresponds to a specific slot in the blockchain.

    When a validator processes a transaction, it checks if the transaction's recentBlockhash is within the most recent
    151 stored hashes in the BlockhashQueue. This period is known as the "max processing age." 

    The expiration is determined by block height rather than real-time.
    A transaction expires when the blockchain reaches a height 151 blocks greater than the block height of the 
    transaction's recentBlockhash
    """

    instructions: list[Instruction]
    """List of program instructions that will be executed in sequence and committed in one atomic transaction if all succeed."""

    addressTableLookups: list[AddressTableLookup] | None = None
    """
    List of address table lookups used by a transaction to dynamically load addresses from on-chain address lookup tables.
    Undefined if maxSupportedTransactionVersion is not set.
    """


class Transaction(Struct, forbid_unknown_fields=True):
    message: TransactionMessage
    """Defines the content of the transaction"""

    signatures: list[str]
    """
    A list of base-58 encoded signatures applied to the transaction.
    The list is always of length message.header.numRequiredSignatures and not empty.
    The signature at index i corresponds to the public key at index i in message.accountKeys.
    The first one is used as the transaction id.
    """


class TransactionWrapper(Struct, forbid_unknown_fields=True):
    transaction: Transaction
    """`Transaction` object, either in JSON format or encoded binary data, depending on the encoding parameter"""

    meta: TransactionMeta
    """Transaction status metadata object, present if `transactionDetails` is set to 'full'"""

    version: Literal["legacy"] | int
    """Transaction version, undefined if `maxSupportedTransactionVersion` is not set in request params"""

    def extend_keys_with_lookup_table_accounts(self, is_first_pass: bool = True):
        if is_first_pass:
            self.transaction.message.accountKeys += self.meta.loadedAddresses.writable + self.meta.loadedAddresses.readonly

            for instruction in self.transaction.message.instructions:
                instruction.accounts = [self.transaction.message.accountKeys[account] for account in
                                        instruction.accounts]

            if self.meta.innerInstructions:
                for ix in self.meta.innerInstructions:
                    for inner_ix in ix.instructions:
                        inner_ix.accounts = [self.transaction.message.accountKeys[account] for account in
                                             inner_ix.accounts]


class Block(Struct, forbid_unknown_fields=True):
    previousBlockhash: str
    """
    The blockhash of this block's parent, as base-58 encoded string;
    if the parent block is not available due to ledger cleanup, this field will return "11111111111111111111111111111111"
    """

    blockhash: str
    """The blockhash of this block, as base-58 encoded string"""

    parentSlot: int  # u64
    """The slot index of this block's parent"""

    transactions: list[TransactionWrapper]
    """
    Present if 'full' transaction details were requested;
    an array of JSON objects containing either JSON object (dict) if JSONParsed requested, or tuple[string, encoding]
    """

    blockTime: int | None  # i64
    """Estimated production time, as Unix timestamp (seconds since the Unix epoch), null if not available"""

    blockHeight: int | None  # u64
    """"The number of blocks beneath this block"""

    numRewardPartitions: int | None = None

    rewards: list[dict] = field(default_factory=list)

    slot: int = -1  # placeholder to be set post initialization
