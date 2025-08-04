"""SPL Token coder for parsing token program instructions."""

from __future__ import annotations
from typing import Optional
import base64

from msgspec import Struct
from borsh_construct import CStruct, U8, U64
from construct import Bytes, Optional as OptionalConstruct
from loguru import logger

from ionic_solana_indexer.coders.base_coder import BaseCoder, ParsedInstruction, TransactionContext
from ionic_solana_indexer.block.transactions.raw_transaction import InstructionField

SPL_TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"

# Borsh layouts for SPL Token instructions
initialize_mint_layout = CStruct(
    "discriminator" / U8,
    "decimals" / U8,
    "mint_authority" / Bytes(32),
    "freeze_authority" / OptionalConstruct(Bytes(32)),
)

mint_to_layout = CStruct(
    "discriminator" / U8,
    "amount" / U64,
)

mint_to_checked_layout = CStruct(
    "discriminator" / U8,
    "amount" / U64,
    "decimals" / U8,
)

burn_layout = CStruct(
    "discriminator" / U8,
    "amount" / U64,
)

burn_checked_layout = CStruct(
    "discriminator" / U8,
    "amount" / U64,
    "decimals" / U8,
)

transfer_layout = CStruct(
    "discriminator" / U8,
    "amount" / U64,
)

transfer_checked_layout = CStruct(
    "discriminator" / U8,
    "amount" / U64,
    "decimals" / U8,
)

initialize_account_3_layout = CStruct(
    "discriminator" / U8,
    "owner" / Bytes(32),
)


class SplTokenInstructionData(Struct):
    """Base class for SPL Token instruction data."""
    discriminator: int


class InitializeMintData(SplTokenInstructionData):
    """Initialize mint instruction data."""
    decimals: int
    mint_authority: str
    freeze_authority: Optional[str] = None


class TransferData(SplTokenInstructionData):
    """Transfer instruction data."""
    amount: int
    decimals: Optional[int] = None


class MintToData(SplTokenInstructionData):
    """Mint to instruction data."""
    amount: int
    decimals: Optional[int] = None


class BurnData(SplTokenInstructionData):
    """Burn instruction data."""
    amount: int
    decimals: Optional[int] = None


class InitializeAccountData(SplTokenInstructionData):
    """Initialize account instruction data."""
    owner: str


def convert_b58_bytes_to_string(b: bytes) -> str:
    """Convert bytes to base58 string."""
    import base58
    return base58.b58encode(b).decode("utf-8")


class SplTokenCoder(BaseCoder):
    """Coder for SPL Token program instructions."""

    def __init__(self):
        super().__init__("SPL_Token", [SPL_TOKEN_PROGRAM_ID])

    def can_handle(self, instruction: InstructionField) -> bool:
        """Check if this coder can handle the instruction."""
        return instruction.programId == SPL_TOKEN_PROGRAM_ID and instruction.data is not None

    def parse_instruction(
            self,
            instruction: InstructionField,
            instruction_index: int,
            context: TransactionContext
    ) -> Optional[ParsedInstruction]:
        """Parse an SPL Token instruction."""
        if not instruction.data or not instruction.accounts:
            return None

        try:
            # Decodes base64 instruction data
            data = base64.b64decode(instruction.data)
            if len(data) == 0:
                return None

            discriminator = int.from_bytes(data[:1], "little")
            accounts = instruction.accounts

            parsed_data = None

            match discriminator:
                case 0:  # InitializeMint
                    if len(accounts) >= 1:
                        decoded = initialize_mint_layout.parse(data)
                        parsed_data = InitializeMintData(
                            discriminator=discriminator,
                            decimals=decoded.decimals,
                            mint_authority=convert_b58_bytes_to_string(decoded.mint_authority),
                            freeze_authority=convert_b58_bytes_to_string(
                                decoded.freeze_authority) if decoded.freeze_authority else None
                        )

                case 3:  # Transfer
                    if len(accounts) >= 3:
                        decoded = transfer_layout.parse(data)
                        parsed_data = TransferData(
                            discriminator=discriminator,
                            amount=decoded.amount
                        )

                case 7:  # MintTo
                    if len(accounts) >= 2:
                        decoded = mint_to_layout.parse(data)
                        parsed_data = MintToData(
                            discriminator=discriminator,
                            amount=decoded.amount
                        )

                case 8:  # Burn
                    if len(accounts) >= 2:
                        decoded = burn_layout.parse(data)
                        parsed_data = BurnData(
                            discriminator=discriminator,
                            amount=decoded.amount
                        )

                case 12:  # TransferChecked
                    if len(accounts) >= 4:
                        decoded = transfer_checked_layout.parse(data)
                        parsed_data = TransferData(
                            discriminator=discriminator,
                            amount=decoded.amount,
                            decimals=decoded.decimals
                        )

                case 14:  # MintToChecked
                    if len(accounts) >= 2:
                        decoded = mint_to_checked_layout.parse(data)
                        parsed_data = MintToData(
                            discriminator=discriminator,
                            amount=decoded.amount,
                            decimals=decoded.decimals
                        )

                case 15:  # BurnChecked
                    if len(accounts) >= 2:
                        decoded = burn_checked_layout.parse(data)
                        parsed_data = BurnData(
                            discriminator=discriminator,
                            amount=decoded.amount,
                            decimals=decoded.decimals
                        )

                case 18:  # InitializeAccount3
                    if len(accounts) >= 2:
                        decoded = initialize_account_3_layout.parse(data)
                        parsed_data = InitializeAccountData(
                            discriminator=discriminator,
                            owner=convert_b58_bytes_to_string(decoded.owner)
                        )

                case 20:  # InitializeMint2
                    if len(accounts) >= 1:
                        decoded = initialize_mint_layout.parse(data)
                        parsed_data = InitializeMintData(
                            discriminator=discriminator,
                            decimals=decoded.decimals,
                            mint_authority=convert_b58_bytes_to_string(decoded.mint_authority),
                            freeze_authority=convert_b58_bytes_to_string(
                                decoded.freeze_authority) if decoded.freeze_authority else None
                        )

            if parsed_data:
                return ParsedInstruction(
                    instruction=instruction,
                    instruction_index=instruction_index,
                    parsed_data=parsed_data,
                    coder_name=self.name
                )

        except Exception as e:
            logger.warning(e)
            pass

        return None

