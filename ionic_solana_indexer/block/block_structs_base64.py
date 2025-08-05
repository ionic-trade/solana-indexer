# Copyright (C) 2025, Ionic.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

"""Definitions derived from the agave core client implementation"""
from typing import Literal, Optional, Any

from msgspec import Struct, field

from ionic_solana_indexer.block.transactions.transaction_errors import TransactionErrorEnum


class TransactionError(Struct, omit_defaults=True):
    InstructionError: Optional[tuple[int, dict | str]] = None
    InsufficientFundsForRent: Optional[dict[Literal["account_index"], int]] = None

    @property
    def inner(self) -> tuple[int, dict | str] | dict[Literal["account_index"], int]:
        if self.InstructionError:
            return self.InstructionError
        return self.InsufficientFundsForRent

    @property
    def error(self) -> tuple[TransactionErrorEnum, dict | str]:
        try:
            return TransactionErrorEnum(self.InstructionError[0]), self.InstructionError[1]
        except ValueError:
            return TransactionErrorEnum.UNKNOWN_ERROR, ""


class Reward(Struct):
    pubkey: str

    lamports: int  # i64

    postBalance: int  # u64

    rewardType: Literal["fee", "rent", "voting", "staking", "Fee", "Rent", "Voting", "Staking"] | None

    commission: int | None  # u8


class UiTokenAmount(Struct, omit_defaults=True):
    amount: str

    decimals: int

    uiAmountString: str

    uiAmount: float | None = None


class TokenBalance(Struct, forbid_unknown_fields=True):
    accountIndex: int

    mint: str

    owner: str | None

    programId: str | None

    uiTokenAmount: UiTokenAmount


class Instruction(Struct, forbid_unknown_fields=False):
    programIdIndex: int

    accounts: Any

    data: str

    stackHeight: int | None


class InnerInstruction(Struct):
    index: int

    instructions: list[Instruction]


class AddressTableLookup(Struct, forbid_unknown_fields=True):
    accountKey: str

    writableIndexes: list[int]

    readonlyIndexes: list[int]


class TransactionHeader(Struct, forbid_unknown_fields=True):
    numRequiredSignatures: int

    numReadonlySignedAccounts: int

    numReadonlyUnsignedAccounts: int


class AccountKey(Struct):
    pubkey: str

    writable: bool

    signer: bool

    source: Literal["transaction"]

class TransactionMessage(Struct):
    accountKeys: list[AccountKey]

    header: TransactionHeader

    recentBlockhash: str

    instructions: list[Instruction]

    addressTableLookups: list[AddressTableLookup] | None = None


class Transaction(Struct):
    signatures: list[str]

    message: TransactionMessage

class ReturnData(Struct):
    programId: str

    data: tuple[str, str]


class LoadedAddresses(Struct):

    writable: list[str]

    readonly: list[str]


class TransactionMeta(Struct, forbid_unknown_fields=True):
    err: TransactionError | str | None

    fee: int

    preBalances: list[int] = field(default_factory=list)

    postBalances: list[int] = field(default_factory=list)

    innerInstructions: list[InnerInstruction] | None = field(default_factory=list)

    preTokenBalances: list[TokenBalance] | None = field(default_factory=list)

    postTokenBalances: list[TokenBalance] | None = field(default_factory=list)

    logMessages: list[str] | None = field(default_factory=list)

    rewards: list[Reward] | None = field(default_factory=list)

    status: dict[Literal["Ok", "Err"], None | TransactionError | str] | None = None

    loadedAddresses: LoadedAddresses | None = None

    returnData: ReturnData | None = None

    computeUnitsConsumed: int | None = None  # u64


class TransactionWrapper(Struct):
    transaction: tuple[str, Literal["base64"]]

    meta: TransactionMeta | None

    version: Literal["legacy"] | int | None

class Block(Struct):
    blockhash: str

    previousBlockhash: str

    parentSlot: int  # u64

    transactions: list[TransactionWrapper]

    blockTime: int | None  # i64

    blockHeight: int | None  # u64

    signatures: list[str] | None = None

    rewards: list[Reward] | None = None
