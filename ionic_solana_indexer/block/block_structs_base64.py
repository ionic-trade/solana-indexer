"""
Definitions derived from the agave core client implementation
"""

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
    """The public key, as base-58 encoded string, of the account that received the reward"""

    lamports: int  # i64
    """number of reward lamports credited or debited by the account, as a i64"""

    postBalance: int  # u64
    """account balance in lamports after the reward was applied"""

    rewardType: Literal["fee", "rent", "voting", "staking", "Fee", "Rent", "Voting", "Staking"] | None
    """type of reward"""

    commission: int | None  # u8
    """vote account commission when the reward was credited, only present for voting and staking rewards"""


class UiTokenAmount(Struct, omit_defaults=True):
    amount: str
    """Raw amount of tokens as a string, ignoring decimals"""

    decimals: int
    """Number of decimals configured for token's mint"""

    uiAmountString: str
    """Token amount as a string, accounting for decimals"""

    uiAmount: float | None = None
    """Token amount as a float, accounting for decimals. DEPRECATED"""


class TokenBalance(Struct, forbid_unknown_fields=True):
    accountIndex: int
    """Index of the account in which the token balance is provided for"""

    mint: str
    """Pubkey of the token's mint"""

    owner: str | None
    """Pubkey of token balance's owner"""

    programId: str | None
    """Pubkey of the Token program that owns the account"""

    uiTokenAmount: UiTokenAmount
    """Token amount information"""


class Instruction(Struct, forbid_unknown_fields=True):
    programIdIndex: int
    """Index into the `message.accountKeys` array indicating the program account that executes this instruction"""

    accounts: Any  # list[int] initially, converted to list[str] after lookup table resolution
    """List of ordered indices into the `message.accountKeys` array indicating which accounts to pass to the program. Can be converted to addresses after lookup table resolution."""

    data: str
    """The program input data encoded in a base-58 string"""

    stackHeight: int | None


class InnerInstruction(Struct):
    index: int
    """Index of the transaction instruction from which the inner instruction(s) originated"""

    instructions: list[Instruction]
    """Ordered list of inner program instructions that were invoked during a single transaction instruction"""


class AddressTableLookup(Struct, forbid_unknown_fields=True):
    accountKey: str
    """base-58 encoded public key for an address lookup table account"""

    writableIndexes: list[int]
    """List of indices used to load addresses of writable accounts from a lookup table"""

    readonlyIndexes: list[int]
    """List of indices used to load addresses of readonly accounts from a lookup table"""


class TransactionHeader(Struct, forbid_unknown_fields=True):
    numRequiredSignatures: int
    """
    The total number of signatures required to make the transaction valid.
    The signatures must match the first numRequiredSignatures of message.accountKeys.
    """

    numReadonlySignedAccounts: int
    """
    The last numReadonlySignedAccounts of the signed keys are read-only accounts.
    Programs may process multiple transactions that load read-only accounts within a single PoH entry,
    but are not permitted to credit or debit lamports or modify account data.
    Transactions targeting the same read-write account are evaluated sequentially.
    """

    numReadonlyUnsignedAccounts: int
    """The last numReadonlyUnsignedAccounts of the unsigned keys are read-only accounts."""


class AccountKey(Struct):
    pubkey: str
    """Public key of the account, as base-58 encoded string"""

    writable: bool
    """Whether the account is writable in the transaction"""

    signer: bool
    """Whether the account is a signer in the transaction"""

    source: Literal["transaction"]


class TransactionMessage(Struct):
    accountKeys: list[AccountKey]
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


class Transaction(Struct):
    signatures: list[str]
    """
    A list of base-58 encoded signatures applied to the transaction.
    The list is always of length message.header.numRequiredSignatures and not empty.
    The signature at index i corresponds to the public key at index i in message.accountKeys.
    The first one is used as the transaction id.
    """

    message: TransactionMessage
    """Defines the content of the transaction"""


class ReturnData(Struct):
    programId: str
    """The program that generated the return data, as base-58 encoded string"""

    data: tuple[str, str]
    """The return data itself, as base-64 encoded binary data"""


class LoadedAddresses(Struct):
    """
    Transaction addresses loaded from address lookup tables.
    Undefined if maxSupportedTransactionVersion is not set in request params,
    or if jsonParsed encoding is set in request params.
    """

    writable: list[str]
    """Ordered list of base-58 encoded addresses for writable accounts"""

    readonly: list[str]
    """Ordered list of base-58 encoded addresses for readonly accounts"""


class TransactionMeta(Struct, forbid_unknown_fields=True):
    err: TransactionError | str | None
    # err: dict[Literal["InstructionError"], tuple[int, dict]] | None
    """Error if transaction failed, null if transaction succeeded"""

    fee: int
    """Fee this transaction was charged, as u64 integer"""

    preBalances: list[int] = field(default_factory=list)
    """Array of u64 account balances from before the transaction was processed"""

    postBalances: list[int] = field(default_factory=list)
    """Array of u64 account balances after the transaction was processed"""

    innerInstructions: list[InnerInstruction] | None = field(default_factory=list)
    """List of inner instructions or None if inner instruction recording was not enabled"""

    preTokenBalances: list[TokenBalance] | None = field(default_factory=list)
    """List of token balances from before the transaction was processed, omitted if token balances were not requested"""

    postTokenBalances: list[TokenBalance] | None = field(default_factory=list)
    """List of token balances from after the transaction was processed, omitted if token balances were not requested"""

    logMessages: list[str] | None = field(default_factory=list)
    """Array of string log messages or None if log message recording was not enabled"""

    rewards: list[Reward] | None = field(default_factory=list)
    """Transaction-level rewards, populated if rewards are requested"""

    status: dict[Literal["Ok", "Err"], None | TransactionError | str] | None = None
    # status: Literal["Ok"] | TransactionError | None = None
    """DEPRECATED: Transaction status"""

    loadedAddresses: LoadedAddresses | None = None
    """
    Transaction addresses loaded from address lookup tables.
    Undefined if maxSupportedTransactionVersion is not set in request params,
    or if jsonParsed encoding is set in request params.
    """

    returnData: ReturnData | None = None
    """The most-recent return data generated by an instruction in the transaction"""

    computeUnitsConsumed: int | None = None  # u64
    """Number of compute units consumed by the transaction"""


class TransactionWrapper(Struct):
    transaction: tuple[str, Literal["base64"]]
    """`Transaction` object, either in JSON format or encoded binary data, depending on the encoding parameter"""

    meta: TransactionMeta | None
    """Transaction status metadata object, present if `transactionDetails` is set to 'full'"""

    version: Literal["legacy"] | int | None
    """Transaction version, undefined if `maxSupportedTransactionVersion` is not set in request params"""


class Block(Struct):
    blockhash: str
    """The blockhash of this block, as base-58 encoded string"""

    previousBlockhash: str
    """
    The blockhash of this block's parent, as base-58 encoded string;
    if the parent block is not available due to ledger cleanup, this field will return "11111111111111111111111111111111"
    """

    parentSlot: int  # u64
    """The slot index of this block's parent"""

    transactions: list[TransactionWrapper]
    """
    Present if 'full' transaction details were requested;
    an array of JSON objects containing either JSON object (dict) or tuple[string, encoding]
    """

    blockTime: int | None  # i64
    """Estimated production time, as Unix timestamp (seconds since the Unix epoch), null if not available"""

    blockHeight: int | None  # u64
    """The number of blocks beneath this block"""

    signatures: list[str] | None = None
    """
    Present if 'signatures' are requested for transaction details;
    an array of signatures strings corresponding to the the transaction order in the block
    """

    rewards: list[Reward] | None = None
    """block-level rewards, present if rewards are requested"""
