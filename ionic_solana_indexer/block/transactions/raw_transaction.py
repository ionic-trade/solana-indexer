"""RawTransaction structures for parsing Solana JSON-RPC transaction responses."""

from __future__ import annotations
from typing import Any, Optional
from msgspec import Struct


class UiTokenAmount(Struct):
    """Token amount with UI representation."""
    amount: str
    decimals: int
    uiAmount: float | None
    uiAmountString: str


class TokenBalanceChange(Struct):
    """Token balance change information."""
    accountIndex: int
    mint: str
    owner: str
    programId: str
    uiTokenAmount: UiTokenAmount


class InstructionField(Struct):
    """Individual instruction within a transaction."""
    programId: str
    stackHeight: int | None = None
    program: Optional[str] = None
    parsed: Optional[dict | str] = None
    data: Optional[str] = None
    accounts: Optional[list[str]] = None

    def is_parsed(self) -> bool:
        """Check if instruction has parsed data."""
        match self.parsed:
            case None:
                return False
            case str():
                return False
            case dict():
                return True
            case _:
                raise ValueError(f"Unexpected type for {self.parsed=}")


class InnerInstruction(Struct):
    """Inner instruction with index and instruction list."""
    index: int
    instructions: list[InstructionField]


class AccountKey(Struct):
    """Account key with metadata."""
    pubkey: str
    signer: bool
    source: str
    writable: bool


class TransactionMessage(Struct):
    """Transaction message containing instructions and account keys."""
    accountKeys: list[AccountKey]
    instructions: list[InstructionField]
    recentBlockhash: str
    addressTableLookups: Optional[list[dict]] = None


class ParsedTransaction(Struct):
    """Parsed transaction with message and signatures."""
    message: TransactionMessage
    signatures: list[str]


class TransactionsMeta(Struct):
    """Transaction metadata including balances and logs."""
    computeUnitsConsumed: int
    fee: int
    innerInstructions: list[InnerInstruction]
    logMessages: list[str]
    postBalances: list[int]
    postTokenBalances: list[TokenBalanceChange]
    preBalances: list[int]
    preTokenBalances: list[TokenBalanceChange]
    status: dict
    rewards: list[Any] | None
    err: dict | None
    costUnits: Optional[int] = None


class TransactionResult(Struct):
    """Transaction result from JSON-RPC response."""
    blockTime: int
    meta: TransactionsMeta
    slot: int
    transaction: ParsedTransaction
    version: int


class RawTransaction(Struct):
    """Complete raw transaction from Solana JSON-RPC response."""
    jsonrpc: str
    result: TransactionResult
    id: int

    @property
    def main_signature(self) -> str:
        """Get the main transaction signature."""
        if self.result.transaction.signatures:
            return self.result.transaction.signatures[0]
        return "unknown_signature"

    @property
    def slot(self) -> int:
        """Get the transaction slot."""
        return self.result.slot

    @property
    def block_time(self) -> int:
        """Get the block timestamp."""
        return self.result.blockTime

    @property
    def is_successful(self) -> bool:
        """Check if transaction was successful."""
        return self.result.meta.err is None

    @property
    def all_instructions(self) -> list[InstructionField]:
        """Gets all instructions (outer + inner) in execution order."""
        all_instructions = []
        outer_instructions = self.result.transaction.message.instructions
        inner_instructions_map = {
            inner_ix.index: inner_ix.instructions
            for inner_ix in self.result.meta.innerInstructions
        }

        for i, outer_instruction in enumerate(outer_instructions):
            all_instructions.append(outer_instruction)

            if i in inner_instructions_map:
                inner_instructions = inner_instructions_map[i]
                sorted_inner = sorted(
                    inner_instructions,
                    key=lambda ix: ix.stackHeight if ix.stackHeight is not None else float('inf')
                )
                all_instructions.extend(sorted_inner)

        return all_instructions

    @property
    def signers(self) -> list[str]:
        """Gets all signer account keys."""
        return [acc.pubkey for acc in self.result.transaction.message.accountKeys if acc.signer]

    def includes_program(self, program_id: str) -> bool:
        """Checks if transaction involves a specific program."""
        if any(ix.programId == program_id for ix in self.result.transaction.message.instructions):
            return True

        for inner_ix in self.result.meta.innerInstructions:
            if any(ix.programId == program_id for ix in inner_ix.instructions):
                return True

        return False

    @property
    def native_transfers(self) -> list[dict]:
        """Extracts native SOL transfers from inner instructions."""
        transfers = []
        for inner_ix in self.result.meta.innerInstructions:
            for ix in inner_ix.instructions:
                if ix.is_parsed() and isinstance(ix.parsed, dict) and ix.parsed.get("type") == "transfer":
                    info = ix.parsed.get("info", {})
                    if "lamports" in info:
                        transfers.append({
                            "from": info["source"],
                            "to": info.get("destination") or info.get("newAccount"),
                            "amount": info["lamports"],
                            "instruction_index": inner_ix.index
                        })
        return transfers

    @property
    def token_transfers(self) -> list[dict]:
        """Extracts token transfers from balance changes."""
        transfers = []
        accounts = [acc.pubkey for acc in self.result.transaction.message.accountKeys]

        # Creates mapping of token balance changes
        pre_balances = {
            (accounts[tb.accountIndex], tb.mint): tb.uiTokenAmount.amount
            for tb in self.result.meta.preTokenBalances
        }

        post_balances = {
            (accounts[tb.accountIndex], tb.mint): tb.uiTokenAmount.amount
            for tb in self.result.meta.postTokenBalances
        }

        # Finds all unique (account, mint) pairs
        all_pairs = set(pre_balances.keys()) | set(post_balances.keys())

        for account, mint in all_pairs:
            pre_amount = int(pre_balances.get((account, mint), "0"))
            post_amount = int(post_balances.get((account, mint), "0"))

            if pre_amount != post_amount:
                transfers.append({
                    "account": account,
                    "mint": mint,
                    "amount_change": post_amount - pre_amount,
                    "pre_amount": pre_amount,
                    "post_amount": post_amount
                })

        return transfers