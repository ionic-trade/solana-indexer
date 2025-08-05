# Copyright (C) 2025, Ionic.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.


"""Convert Block transactions to RawTransaction format."""

from typing import List, Optional, Tuple
import base64
import base58
from loguru import logger

from ionic_solana_indexer.block.block_structs_base64 import Block, TransactionWrapper
from ionic_solana_indexer.block.transactions.raw_transaction import (
    RawTransaction, TransactionResult, ParsedTransaction, TransactionMessage,
    TransactionsMeta, InstructionField, InnerInstruction,
    TokenBalanceChange, UiTokenAmount, AccountKey
)


class SolanaTransactionDecoder:
    """Decoder for Solana transaction binary format."""

    @staticmethod
    def decode_compact_u16(data: bytes, offset: int) -> Tuple[int, int]:
        """Decode compact u16 encoding."""
        if offset >= len(data):
            return 0, offset

        first_byte = data[offset]
        if first_byte < 0x80:
            return first_byte, offset + 1
        elif first_byte < 0xc0:
            if offset + 1 >= len(data):
                return 0, offset
            return ((first_byte & 0x7f) << 8) | data[offset + 1], offset + 2
        else:
            if offset + 2 >= len(data):
                return 0, offset
            return ((first_byte & 0x3f) << 16) | (data[offset + 1] << 8) | data[offset + 2], offset + 3

    @staticmethod
    def decode_pubkey(data: bytes, offset: int) -> Tuple[str, int]:
        """Decode a 32-byte public key to base58 string."""
        if offset + 32 > len(data):
            return "invalid_pubkey", offset

        pubkey_bytes = data[offset:offset + 32]
        pubkey_b58 = base58.b58encode(pubkey_bytes).decode('utf-8')
        return pubkey_b58, offset + 32

    @staticmethod
    def decode_transaction(tx_data: str) -> Tuple[List[str], List[AccountKey], List[InstructionField], str]:
        """Decode full transaction from base64 data."""
        try:
            tx_bytes = base64.b64decode(tx_data)
            offset = 0

            if len(tx_bytes) < 1:
                return [], [], [], ""

            # Decoding signatures
            num_signatures = tx_bytes[offset]
            offset += 1

            signatures = []
            for i in range(num_signatures):
                if offset + 64 > len(tx_bytes):
                    break
                sig_bytes = tx_bytes[offset:offset + 64]
                sig_b58 = base58.b58encode(sig_bytes).decode('utf-8')
                signatures.append(sig_b58)
                offset += 64

            # Decoding message header
            if offset + 3 > len(tx_bytes):
                return signatures, [], [], ""

            num_required_signatures = tx_bytes[offset]
            num_readonly_signed_accounts = tx_bytes[offset + 1]
            num_readonly_unsigned_accounts = tx_bytes[offset + 2]
            offset += 3

            # Decoding account keys
            num_accounts, offset = SolanaTransactionDecoder.decode_compact_u16(tx_bytes, offset)

            account_keys = []
            account_addresses = []

            for i in range(num_accounts):
                pubkey, offset = SolanaTransactionDecoder.decode_pubkey(tx_bytes, offset)
                account_addresses.append(pubkey)

                # Determine account properties
                is_signer = i < num_required_signatures
                is_writable = (
                        (i < num_required_signatures - num_readonly_signed_accounts) or
                        (i >= num_required_signatures and i < num_accounts - num_readonly_unsigned_accounts)
                )

                account_keys.append(AccountKey(
                    pubkey=pubkey,
                    signer=is_signer,
                    writable=is_writable,
                    source="transaction"
                ))

            # 4. Decode recent blockhash
            recent_blockhash = ""
            if offset + 32 <= len(tx_bytes):
                blockhash_bytes = tx_bytes[offset:offset + 32]
                recent_blockhash = base58.b58encode(blockhash_bytes).decode('utf-8')
                offset += 32

            # 5. Decode instructions
            num_instructions, offset = SolanaTransactionDecoder.decode_compact_u16(tx_bytes, offset)

            instructions = []
            for i in range(num_instructions):
                if offset >= len(tx_bytes):
                    break

                # Program ID index
                program_id_index = tx_bytes[offset]
                offset += 1

                # Account indices
                num_account_indices, offset = SolanaTransactionDecoder.decode_compact_u16(tx_bytes, offset)
                account_indices = []

                for j in range(num_account_indices):
                    if offset < len(tx_bytes):
                        account_indices.append(tx_bytes[offset])
                        offset += 1

                # Instruction data
                data_len, offset = SolanaTransactionDecoder.decode_compact_u16(tx_bytes, offset)
                instruction_data = ""

                if offset + data_len <= len(tx_bytes):
                    data_bytes = tx_bytes[offset:offset + data_len]
                    instruction_data = base64.b64encode(data_bytes).decode('utf-8')
                    offset += data_len

                program_id = account_addresses[program_id_index] if program_id_index < len(
                    account_addresses) else "unknown"

                account_addrs = []
                for idx in account_indices:
                    if idx < len(account_addresses):
                        account_addrs.append(account_addresses[idx])

                instructions.append(InstructionField(
                    programId=program_id,
                    accounts=account_addrs,
                    data=instruction_data,
                    stackHeight=1  # Outer instructions always have stackHeight=1
                ))

            return signatures, account_keys, instructions, recent_blockhash

        except Exception as e:
            logger.debug(f"Failed to decode transaction: {e}")
            return [], [], [], ""


class TransactionConverter:
    """Converts base64 block transactions to RawTransaction format."""

    @staticmethod
    def extract_main_signature(tx_data: str) -> str:
        """Extract just the main signature from base64 encoded transaction data."""
        try:
            signatures = TransactionConverter.extract_signatures_from_base64(tx_data)
            return signatures[0] if signatures else "no_signature"
        except Exception as e:
            logger.debug(f"Failed to extract main signature: {e}")
            return "signature_extraction_failed"

    @staticmethod
    def extract_signatures_from_base64(tx_data: str) -> List[str]:
        """Extract signatures from base64 encoded transaction data."""
        try:
            tx_bytes = base64.b64decode(tx_data)

            if len(tx_bytes) < 1:
                return ["failed_to_decode"]

            num_signatures = tx_bytes[0]

            if num_signatures == 0:
                return ["no_signatures"]

            signatures = []
            offset = 1

            for i in range(num_signatures):
                if offset + 64 <= len(tx_bytes):
                    sig_bytes = tx_bytes[offset:offset + 64]
                    sig_b58 = base58.b58encode(sig_bytes).decode('utf-8')
                    signatures.append(sig_b58)
                    offset += 64
                else:
                    signatures.append("incomplete_signature")

            return signatures

        except Exception as e:
            logger.debug(f"Failed to extract signatures: {e}")
            return ["signature_extraction_failed"]

    @staticmethod
    def convert_block_to_raw_transactions(block: Block, slot: int) -> List[RawTransaction]:
        """Converts all transactions in a block to RawTransaction format."""
        raw_transactions = []

        for i, tx_wrapper in enumerate(block.transactions):
            try:
                raw_tx = TransactionConverter.convert_transaction_wrapper(
                    tx_wrapper, slot, block.blockTime, i
                )
                if raw_tx:
                    raw_transactions.append(raw_tx)
            except Exception as e:
                logger.warning(f"Failed to convert transaction {i} in slot {slot}: {e}")
                continue

        return raw_transactions

    @staticmethod
    def convert_transaction_wrapper(
            tx_wrapper: TransactionWrapper,
            slot: int,
            block_time: Optional[int],
            tx_index: int
    ) -> Optional[RawTransaction]:
        """Converts a single TransactionWrapper to RawTransaction."""

        if not tx_wrapper.transaction or len(tx_wrapper.transaction) < 2:
            return None

        try:
            # Decoding full transaction from base64
            signatures, account_keys, instructions, recent_blockhash = SolanaTransactionDecoder.decode_transaction(
                tx_wrapper.transaction[0]
            )

            # Handle address lookup tables if present
            address_table_lookups = None
            extended_account_keys = account_keys.copy()

            if tx_wrapper.meta and hasattr(tx_wrapper.meta, 'loadedAddresses') and tx_wrapper.meta.loadedAddresses:
                # Add loaded addresses from lookup tables
                loaded_addresses = tx_wrapper.meta.loadedAddresses

                # Add writable accounts from lookup tables
                for addr in (loaded_addresses.writable or []):
                    extended_account_keys.append(AccountKey(
                        pubkey=addr,
                        signer=False,
                        writable=True,
                        source="lookupTable"
                    ))

                # Add readonly accounts from lookup tables  
                for addr in (loaded_addresses.readonly or []):
                    extended_account_keys.append(AccountKey(
                        pubkey=addr,
                        signer=False,
                        writable=False,
                        source="lookupTable"
                    ))

            transaction_message = TransactionMessage(
                accountKeys=extended_account_keys,
                instructions=instructions,
                recentBlockhash=recent_blockhash,
                addressTableLookups=address_table_lookups
            )

            parsed_transaction = ParsedTransaction(
                message=transaction_message,
                signatures=signatures
            )

            # Converts meta if available
            meta = None
            if tx_wrapper.meta:
                # Converts token balances
                pre_token_balances = [
                    TokenBalanceChange(
                        accountIndex=tb.accountIndex,
                        mint=tb.mint,
                        owner=tb.owner or "",
                        programId=tb.programId or "",
                        uiTokenAmount=UiTokenAmount(
                            amount=tb.uiTokenAmount.amount,
                            decimals=tb.uiTokenAmount.decimals,
                            uiAmount=tb.uiTokenAmount.uiAmount,
                            uiAmountString=tb.uiTokenAmount.uiAmountString
                        )
                    )
                    for tb in (tx_wrapper.meta.preTokenBalances or [])
                ]

                post_token_balances = [
                    TokenBalanceChange(
                        accountIndex=tb.accountIndex,
                        mint=tb.mint,
                        owner=tb.owner or "",
                        programId=tb.programId or "",
                        uiTokenAmount=UiTokenAmount(
                            amount=tb.uiTokenAmount.amount,
                            decimals=tb.uiTokenAmount.decimals,
                            uiAmount=tb.uiTokenAmount.uiAmount,
                            uiAmountString=tb.uiTokenAmount.uiAmountString
                        )
                    )
                    for tb in (tx_wrapper.meta.postTokenBalances or [])
                ]

                # Converts inner instructions and extract program IDs from logs
                inner_instructions = []
                if tx_wrapper.meta.innerInstructions:
                    for inner_ix in tx_wrapper.meta.innerInstructions:
                        instructions = []
                        for ix in inner_ix.instructions:
                            # Here will be using id from each parser
                            program_id = "unknown"

                            instructions.append(InstructionField(
                                programId=program_id,
                                stackHeight=ix.stackHeight,
                                data=ix.data
                            ))

                        inner_instructions.append(InnerInstruction(
                            index=inner_ix.index,
                            instructions=instructions
                        ))

                meta = TransactionsMeta(
                    computeUnitsConsumed=tx_wrapper.meta.computeUnitsConsumed or 0,
                    fee=tx_wrapper.meta.fee,
                    innerInstructions=inner_instructions,
                    logMessages=tx_wrapper.meta.logMessages or [],
                    postBalances=tx_wrapper.meta.postBalances or [],
                    postTokenBalances=post_token_balances,
                    preBalances=tx_wrapper.meta.preBalances or [],
                    preTokenBalances=pre_token_balances,
                    status={"Ok": None} if tx_wrapper.meta.err is None else {"Err": tx_wrapper.meta.err},
                    rewards=tx_wrapper.meta.rewards,
                    err=tx_wrapper.meta.err
                )

            transaction_result = TransactionResult(
                blockTime=block_time or 0,
                meta=meta,
                slot=slot,
                transaction=parsed_transaction,
                version=tx_wrapper.version if isinstance(tx_wrapper.version, int) else 0
            )

            raw_transaction = RawTransaction(
                jsonrpc="2.0",
                result=transaction_result,
                id=tx_index
            )

            return raw_transaction

        except Exception as e:
            logger.error(f"Error converting transaction wrapper: {e}")
            return None
