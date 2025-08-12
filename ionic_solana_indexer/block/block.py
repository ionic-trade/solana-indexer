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

    header: TransactionHeader

    recentBlockhash: str

    instructions: list[Instruction]

    addressTableLookups: list[AddressTableLookup] | None = None


class Transaction(Struct, forbid_unknown_fields=True):
    message: TransactionMessage

    signatures: list[str]


class TransactionWrapper(Struct, forbid_unknown_fields=True):
    transaction: Transaction

    meta: TransactionMeta

    version: Literal["legacy"] | int

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

    blockhash: str

    parentSlot: int  # u64

    transactions: list[TransactionWrapper]

    blockTime: int | None  # i64

    blockHeight: int | None  # u64

    numRewardPartitions: int | None = None

    rewards: list[dict] = field(default_factory=list)

    slot: int = -1  # placeholder to be set post initialization
