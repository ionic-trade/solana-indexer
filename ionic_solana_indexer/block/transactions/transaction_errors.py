# Copyright (C) 2025, Ionic.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

"""TransactionErrorEnum class, an enumeration of possible transaction errors"""
from __future__ import annotations

from enum import IntEnum
from typing import Any


class TransactionErrorEnum(IntEnum):
    """
    Enumeration of possible transaction errors.
    """

    SUCCESS = -1
    """The transaction executed successfully"""

    ACCOUNT_IN_USE = 0
    """An account is already being processed in another transaction in a way
    that does not support parallelism"""

    ACCOUNT_LOADED_TWICE = 1
    """A `Pubkey` appears twice in the transaction's `account_keys`. Instructions can reference
    `Pubkey`s more than once but the message must contain a list with no duplicate keys"""

    ACCOUNT_NOT_FOUND = 2
    """Attempt to debit an account but found no record of a prior credit."""

    PROGRAM_ACCOUNT_NOT_FOUND = 3
    """Attempt to load a program that does not exist"""

    INSUFFICIENT_FUNDS_FOR_FEE = 4
    """The from `Pubkey` does not have sufficient balance to pay the fee to schedule the transaction"""

    INVALID_ACCOUNT_FOR_FEE = 5
    """This account may not be used to pay transaction fees"""

    ALREADY_PROCESSED = 6
    """The bank has seen this transaction before. This can occur under normal operation
    when a UDP packet is duplicated, as a user error from a client not updating
    its `recent_blockhash`, or as a double-spend attack."""

    BLOCKHASH_NOT_FOUND = 7
    """The bank has not seen the given `recent_blockhash` or the transaction is too old and
    the `recent_blockhash` has been discarded."""

    INSTRUCTION_ERROR = 8
    """An error occurred while processing an instruction. The first element of the tuple
    indicates the instruction index in which the error occurred."""

    CALL_CHAIN_TOO_DEEP = 9
    """Loader call chain is too deep"""

    MISSING_SIGNATURE_FOR_FEE = 10
    """Transaction requires a fee but has no signature present"""

    INVALID_ACCOUNT_INDEX = 11
    """Transaction contains an invalid account reference"""

    SIGNATURE_FAILURE = 12
    """Transaction did not pass signature verification"""

    INVALID_PROGRAM_FOR_EXECUTION = 13
    """This program may not be used for executing instructions"""

    SANITIZE_FAILURE = 14
    """Transaction failed to sanitize accounts offsets correctly
    implies that account locks are not taken for this TX, and should
    not be unlocked."""

    CLUSTER_MAINTENANCE = 15
    """Transactions are currently disabled due to cluster maintenance"""

    ACCOUNT_BORROW_OUTSTANDING = 16
    """Transaction processing left an account with an outstanding borrowed reference"""

    WOULD_EXCEED_MAX_BLOCK_COST_LIMIT = 17
    """Transaction would exceed max Block Cost Limit"""

    UNSUPPORTED_VERSION = 18
    """Transaction version is unsupported"""

    INVALID_WRITABLE_ACCOUNT = 19
    """Transaction loads a writable account that cannot be written"""

    WOULD_EXCEED_MAX_ACCOUNT_COST_LIMIT = 20
    """Transaction would exceed max account limit within the block"""

    WOULD_EXCEED_MAX_ACCOUNT_DATA_COST_LIMIT = 21
    """Transaction would exceed max account data limit within the block"""

    UNKNOWN_ERROR = 22
    """An unknown error occurred while processing the transaction"""

    CUSTOM_ERROR = 23
    """A custom error occurred while processing the transaction"""

    MAX_LOADED_ACCOUNTS_DATA_SIZE_EXCEEDED = 23

    @classmethod
    def handle_error_field(cls, field_value: Any) -> TransactionErrorEnum:
        if isinstance(field_value, dict):
            match field_value:
                case {"InstructionError": _}:
                    return TransactionErrorEnum.INSTRUCTION_ERROR
                case {"InsufficientFundsForRent": _}:
                    return TransactionErrorEnum.INSUFFICIENT_FUNDS_FOR_FEE
                case _:
                    raise ValueError(f"Unknown error field {field_value}")

        if field_value is None:
            return TransactionErrorEnum.SUCCESS
        elif isinstance(field_value, str):
            if field_value == "MaxLoadedAccountsDataSizeExceeded":
                return TransactionErrorEnum.MAX_LOADED_ACCOUNTS_DATA_SIZE_EXCEEDED
            elif field_value == "ProgramAccountNotFound":
                return TransactionErrorEnum.PROGRAM_ACCOUNT_NOT_FOUND
            elif field_value == "InvalidProgramForExecution":
                return TransactionErrorEnum.INVALID_PROGRAM_FOR_EXECUTION
            else:
                raise ValueError(f"Unknown error field {field_value}")
        elif field_value.InstructionError:
            return field_value.error[0]
        elif field_value.InsufficientFundsForRent:
            return TransactionErrorEnum.INSUFFICIENT_FUNDS_FOR_FEE

        return TransactionErrorEnum.UNKNOWN_ERROR
