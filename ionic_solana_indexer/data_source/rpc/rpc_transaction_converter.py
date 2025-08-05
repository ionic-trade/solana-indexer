# Copyright (C) 2025, Ionic.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.


"""Convert Block transactions to RawTransaction format."""

from typing import List, Optional, Tuple, NamedTuple
import base64
from loguru import logger
from solders.transaction import VersionedTransaction


class InstructionIndices(NamedTuple):
    """Holds instruction data with account indices instead of resolved addresses."""
    program_id_index: int
    account_indices: List[int]
    data: str

from ionic_solana_indexer.block.block_structs_base64 import Block, TransactionWrapper
from ionic_solana_indexer.block.transactions.raw_transaction import (
    RawTransaction, TransactionResult, ParsedTransaction, TransactionMessage,
    TransactionsMeta, InstructionField, InnerInstruction,
    TokenBalanceChange, UiTokenAmount, AccountKey
)

from ionic_solana_indexer.utils.known_programs import get_program_by_name

logger.add("solana_block_data.log", rotation="10 MB")

class SolanaTransactionDecoder:
    """Decoder for Solana transaction binary format."""
    
    @staticmethod
    def decode_transaction_with_solders(tx_data: str) -> Tuple[List[str], List[AccountKey], List[InstructionIndices], str]:
        """Decode full transaction from base64 data using solders library."""
        logger.info(f"Tx_data: {tx_data}")
        try:
            tx_bytes = base64.b64decode(tx_data)
            logger.debug(f"Decoding transaction with solders: {len(tx_bytes)} bytes")

            versioned_tx = VersionedTransaction.from_bytes(tx_bytes)
            
            signatures = [str(sig) for sig in versioned_tx.signatures]
            
            message = versioned_tx.message
            account_keys = []
            
            for i, pubkey in enumerate(message.account_keys):
                account_keys.append(AccountKey(
                    pubkey=str(pubkey),
                    signer=i < message.header.num_required_signatures,
                    writable=True,
                    source="transaction"
                ))
            
            instructions = []
            for i, instruction in enumerate(message.instructions):
                instructions.append(InstructionIndices(
                    program_id_index=instruction.program_id_index,
                    account_indices=list(instruction.accounts),
                    data=base64.b64encode(instruction.data).decode('utf-8')
                ))
            
            recent_blockhash = str(message.recent_blockhash)
            
            logger.debug(f"Successfully decoded: {len(signatures)} signatures, {len(account_keys)} accounts, {len(instructions)} instructions")
            
            return signatures, account_keys, instructions, recent_blockhash
            
        except Exception as e:
            logger.error(f"Failed to decode transaction with solders: {e}")
            return [], [], [], ""

    @staticmethod
    def build_program_stack_map(logs: List[str]) -> dict[int, str]:
        """Builds a mapping from stack height (depth) to the invoking programId."""
        stack_map: dict[int,str] = {}
        for log in logs:
            if log.startswith("Program ") and " invoke [" in log:
                try:
                    parts = log.split()
                    program_id = parts[1]
                    stack_depth = int(log.split("invoke [")[1].rstrip("]"))
                    stack_map[stack_depth] = program_id
                except Exception:
                    continue
        return stack_map

class TransactionConverter:
    """Converts base64 block transactions to RawTransaction format."""

    @staticmethod
    def convert_block_to_raw_transactions(block: Block, slot: int) -> List[RawTransaction]:
        """Converts all transactions in a block to RawTransaction format."""
        raw_transactions = []
        converter = TransactionConverter()

        for i, tx_wrapper in enumerate(block.transactions):
            try:
                raw_tx = converter.convert_transaction_wrapper(
                    tx_wrapper, slot, block.blockTime, i
                )
                if raw_tx:
                    raw_transactions.append(raw_tx)
            except Exception as e:
                logger.warning(f"Failed to convert transaction {i} in slot {slot}: {e}")
                continue

        return raw_transactions

    def convert_transaction_wrapper(self, tx_wrapper: TransactionWrapper, slot: int, block_time: Optional[int], tx_index: int) -> Optional[RawTransaction]:
        if not tx_wrapper.transaction or len(tx_wrapper.transaction) < 2:
            return None
        try:
            signatures, account_keys, instruction_indices, recent_blockhash = SolanaTransactionDecoder.decode_transaction_with_solders(
                tx_wrapper.transaction[0]
            )
            address_table_lookups = None
            extended_account_keys = account_keys.copy()
            if tx_wrapper.meta and hasattr(tx_wrapper.meta, 'loadedAddresses') and tx_wrapper.meta.loadedAddresses:
                loaded_addresses = tx_wrapper.meta.loadedAddresses
                for addr in (loaded_addresses.writable or []):
                    extended_account_keys.append(AccountKey(pubkey=addr, signer=False, writable=True, source="lookupTable"))
                for addr in (loaded_addresses.readonly or []):
                    extended_account_keys.append(AccountKey(pubkey=addr, signer=False, writable=False, source="lookupTable"))

            instructions = []
            for ix_indices in instruction_indices:

                program_id = extended_account_keys[ix_indices.program_id_index].pubkey if ix_indices.program_id_index < len(extended_account_keys) else "unknown"
                program_name = get_program_by_name(program_id)

                account_addrs = []
                for acc_idx in ix_indices.account_indices:
                    if acc_idx < len(extended_account_keys):
                        account_addrs.append(extended_account_keys[acc_idx].pubkey)

                instruction = InstructionField(
                    programId=program_id,
                    programName=program_name,
                    program=program_name,
                    accounts=account_addrs,
                    data=ix_indices.data,
                    stackHeight=1  
                )


                instructions.append(instruction)
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
            meta = None
            if tx_wrapper.meta:
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
                    ) for tb in (tx_wrapper.meta.preTokenBalances or [])
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
                    ) for tb in (tx_wrapper.meta.postTokenBalances or [])
                ]
                inner_instructions = []
                program_stack_map = SolanaTransactionDecoder.build_program_stack_map(tx_wrapper.meta.logMessages or [])
                if tx_wrapper.meta.innerInstructions:
                    logger.debug(f"Found {tx_wrapper.meta.innerInstructions} instructions")
                    for inner_ix in tx_wrapper.meta.innerInstructions:
                        instructions: List[InstructionField] = []
                        for ix in inner_ix.instructions:
                            program_id = None
                            if ix.stackHeight is not None and ix.stackHeight in program_stack_map:
                                program_id = program_stack_map[ix.stackHeight]
                            if not program_id and hasattr(ix, "programIdIndex"):
                                idx = ix.programIdIndex
                                if isinstance(idx, int) and idx < len(extended_account_keys):
                                    program_id = extended_account_keys[idx].pubkey
                            if not program_id:
                                program_id = "unknown"
                            program_name = get_program_by_name(program_id)
                            account_pubkeys = []
                            for acc_idx in ix.accounts:
                                if acc_idx < len(extended_account_keys):
                                    account_pubkeys.append(extended_account_keys[acc_idx].pubkey)


                            inner_instruction = InstructionField(
                                programId=program_id,
                                programName=program_name,
                                program=program_name,
                                parsed=None,
                                data=ix.data,
                                accounts=account_pubkeys,
                                stackHeight=ix.stackHeight
                            )


                            instructions.append(inner_instruction)
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
