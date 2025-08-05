# Copyright (C) 2025, Ionic.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.


"""Response models for RPC data source."""

from typing import Generic, TypeVar, Any, Dict
from msgspec import Struct

from ionic_solana_indexer.block.block_structs_base64 import Block

T = TypeVar('T')


class RPCError(Struct):
    """RPC error structure."""
    code: int
    message: str
    data: Any = None


class Response(Struct, Generic[T]):
    """Generic RPC response wrapper."""
    jsonrpc: str
    id: int
    result: T = None
    error: RPCError = None

    @property
    def is_success(self) -> bool:
        """Check if response is successful."""
        return self.error is None

    @property
    def is_error(self) -> bool:
        """Check if response has error."""
        return self.error is not None


class BlockResponse(Response[Block]):
    """Typed response for block data."""
    pass


class SlotResponse(Response[int]):
    """Typed response for slot data."""
    pass
