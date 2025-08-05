# Copyright (C) 2025, Ionic.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.


import aiohttp
import msgspec
import os
from typing import Any, Dict, List, Optional
from loguru import logger
from dotenv import load_dotenv

from ionic_solana_indexer.data_source.data_source import BaseDataSource
from ionic_solana_indexer.block.block_structs_base64 import Block
from ionic_solana_indexer.block.transactions.raw_transaction import RawTransaction
from ionic_solana_indexer.data_source.rpc.rpc_transaction_converter import TransactionConverter

load_dotenv()


class RPCRequest(msgspec.Struct):
    method: str
    params: List[Any]
    jsonrpc: str = "2.0"
    id: int = 1


class RPCResponse(msgspec.Struct):
    jsonrpc: str
    id: int
    result: Any = None
    error: Dict[str, Any] = None


class SolanaRPCDataSource(BaseDataSource):
    """Solana RPC data source implementation."""

    def __init__(self, rpc_url: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """Initializes the Solana RPC data source."""
        super().__init__(config)
        self.rpc_url = rpc_url or os.getenv("SOLANA_RPC_URL")
        if not self.rpc_url:
            raise ValueError("RPC URL must be provided either as parameter or SOLANA_RPC_URL environment variable")
        self.session: Optional[aiohttp.ClientSession] = None
        self.encoder = msgspec.json.Encoder()
        self.decoder = msgspec.json.Decoder(RPCResponse)
        self.block_decoder = msgspec.json.Decoder(Block)
        self.converter = TransactionConverter()

    async def connect(self) -> None:
        """Establishes connection to the Solana RPC endpoint."""
        if not self.session:
            self.session = aiohttp.ClientSession()
        self._connected = True
        logger.info(f"Connected to Solana RPC at {self.rpc_url}")

    async def disconnect(self) -> None:
        """Closes connection to the Solana RPC endpoint."""
        if self.session:
            await self.session.close()
            self.session = None
        self._connected = False

    async def _make_rpc_call(self, method: str, params: List[Any]) -> Any:
        """Makes an RPC call to the Solana endpoint using msgspec."""
        if not self.session:
            raise RuntimeError("RPC client not connected")

        request = RPCRequest(method=method, params=params)
        payload_bytes = self.encoder.encode(request)

        headers = {"Content-Type": "application/json"}
        async with self.session.post(self.rpc_url, data=payload_bytes, headers=headers) as response:
            response_bytes = await response.read()
            rpc_response = self.decoder.decode(response_bytes)

            if rpc_response.error:
                raise Exception(f"RPC Error: {rpc_response.error}")

            return rpc_response.result

    async def get_block(self, slot: int) -> List[RawTransaction]:
        """Retrieves transactions from block at the given slot."""
        logger.info(f"Fetching block at slot {slot}")
        result = await self._make_rpc_call("getBlock", [slot, {
            "encoding": "base64",
            "transactionDetails": "full",
            "rewards": True,
            "maxSupportedTransactionVersion": 0
        }])
        block = self.block_decoder.decode(msgspec.json.encode(result))
        logger.success(
            f"Successfully retrieved block {block.blockhash} at slot {slot} with {len(block.transactions)} transactions")

        # Converts block transactions to RawTransaction format
        raw_transactions = self.converter.convert_block_to_raw_transactions(block, slot)
        logger.info(f"Converted {len(raw_transactions)} transactions to RawTransaction format")

        return raw_transactions

    async def get_slot(self) -> int:
        """Get the current slot."""
        result = await self._make_rpc_call("getSlot", [])
        logger.debug(f"Current slot: {result}")
        return result

    async def health_check(self) -> bool:
        """Perform a health check on the RPC endpoint."""
        if not self.is_connected:
            return False

        try:
            await self.get_slot()
            return True
        except Exception as e:
            logger.error(e)
            return False
