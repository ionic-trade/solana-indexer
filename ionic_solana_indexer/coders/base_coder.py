# Copyright (C) 2025, Ionic.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.


"""Abstract base class for instruction coders."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Optional

from ionic_solana_indexer.block.transactions.raw_transaction import InstructionField, RawTransaction


class ParsedInstruction:
    """Container for a parsed instruction with metadata."""

    def __init__(
            self,
            instruction: InstructionField,
            instruction_index: int,
            parsed_data: Any,
            coder_name: str
    ):
        self.instruction = instruction
        self.instruction_index = instruction_index
        self.parsed_data = parsed_data
        self.coder_name = coder_name


class TransactionContext:
    """Context information available to coders during parsing."""

    def __init__(self, raw_transaction: RawTransaction):
        self.raw_transaction = raw_transaction
        self.slot = raw_transaction.slot
        self.block_time = raw_transaction.block_time
        self.main_signature = raw_transaction.main_signature
        self.is_successful = raw_transaction.is_successful
        self.signers = raw_transaction.signers
        self.native_transfers = raw_transaction.native_transfers
        self.token_transfers = raw_transaction.token_transfers


class BaseCoder(ABC):
    """Abstract base class for instruction coders.

    Each coder is responsible for:
    1. Detecting if it can handle a specific instruction
    2. Parsing the instruction data into meaningful events
    3. Emitting normalized events for downstream processing
    """

    def __init__(self, name: str, program_ids: list[str]):
        """Initialize the coder.

        Args:
            name: Human-readable name for this coder
            program_ids: List of program IDs this coder can handle
        """
        self.name = name
        self.program_ids = set(program_ids)

    @abstractmethod
    def can_handle(self, instruction: InstructionField) -> bool:
        """Check if this coder can handle the given instruction.

        Args:
            instruction: The instruction to check

        Returns:
            True if this coder can handle the instruction, False otherwise
        """
        pass

    @abstractmethod
    def parse_instruction(
            self,
            instruction: InstructionField,
            instruction_index: int,
            context: TransactionContext
    ) -> Optional[ParsedInstruction]:
        """Parse an instruction into structured data.

        Args:
            instruction: The instruction to parse
            instruction_index: Index of this instruction in the transaction
            context: Transaction context for additional information

        Returns:
            ParsedInstruction if successfully parsed, None otherwise
        """
        pass

    def supports_program(self, program_id: str) -> bool:
        """Check if this coder supports a specific program ID.

        Args:
            program_id: The program ID to check

        Returns:
            True if this coder supports the program, False otherwise
        """
        return program_id in self.program_ids

    def parse_transaction(self, raw_transaction: RawTransaction) -> list[ParsedInstruction]:
        """Parse all relevant instructions in a transaction.

        Args:
            raw_transaction: The transaction to parse

        Returns:
            List of parsed instructions
        """
        context = TransactionContext(raw_transaction)
        parsed_instructions = []

        for i, instruction in enumerate(raw_transaction.all_instructions):
            if self.can_handle(instruction):
                parsed = self.parse_instruction(instruction, i, context)
                if parsed:
                    parsed_instructions.append(parsed)

        return parsed_instructions


class CoderRegistry:
    """Registry for managing and accessing coders."""

    def __init__(self):
        self._coders: list[BaseCoder] = []
        self._program_to_coders: dict[str, list[BaseCoder]] = {}

    def register(self, coder: BaseCoder) -> None:
        """Register a new coder.

        Args:
            coder: The coder to register
        """
        self._coders.append(coder)

        # Update program ID mapping
        for program_id in coder.program_ids:
            if program_id not in self._program_to_coders:
                self._program_to_coders[program_id] = []
            self._program_to_coders[program_id].append(coder)

    def get_coders_for_program(self, program_id: str) -> list[BaseCoder]:
        """Get all coders that can handle a specific program.

        Args:
            program_id: The program ID to look up

        Returns:
            List of coders that can handle the program
        """
        return self._program_to_coders.get(program_id, [])

    def get_coders_for_instruction(self, instruction: InstructionField) -> list[BaseCoder]:
        """Get all coders that can handle a specific instruction.

        Args:
            instruction: The instruction to check

        Returns:
            List of coders that can handle the instruction
        """
        potential_coders = self.get_coders_for_program(instruction.programId)
        return [coder for coder in potential_coders if coder.can_handle(instruction)]

    def get_all_coders(self) -> list[BaseCoder]:
        """Get all registered coders.

        Returns:
            List of all registered coders
        """
        return self._coders.copy()

    def parse_transaction(self, raw_transaction: RawTransaction) -> dict[str, list[ParsedInstruction]]:
        """Parse a transaction using all relevant coders.

        Args:
            raw_transaction: The transaction to parse

        Returns:
            Dictionary mapping coder names to their parsed instructions
        """
        results = {}

        for coder in self._coders:
            parsed_instructions = coder.parse_transaction(raw_transaction)
            if parsed_instructions:
                results[coder.name] = parsed_instructions

        return results
