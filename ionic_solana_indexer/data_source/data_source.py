from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ionic_solana_indexer.block.transactions.raw_transaction import RawTransaction


class BaseDataSource(ABC):
    """Abstract base class for all data sources in the Solana indexer.

       Each data source should inherit this class.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initializes the data source with optional configuration."""
        self.config = config or {}
        self._connected = False
    
    @abstractmethod
    async def connect(self) -> None:
        """Establishes connection to the data source."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Closes connection to the data source."""
        pass
    
    @abstractmethod
    async def get_block(self, slot: int) -> List[RawTransaction]:
        """Retrieves transactions from block at the given slot."""
        pass

    @property
    def is_connected(self) -> bool:
        """Checks if the data source is connected."""
        return self._connected
    
    async def health_check(self) -> bool:
        """Performs a health check on the data source."""
        return self.is_connected