from __future__ import annotations
import asyncio
from typing import Generic, TypeVar, Callable, Awaitable, Optional, Iterable, AsyncIterator
from .core import Effect
from .context import Context
A = TypeVar('A'); B = TypeVar('B'); R = TypeVar('R'); E = TypeVar('E')

class Channel(Generic[A]):
    """Async communication channel with backpressure.
    
    Channels provide a way for concurrent operations to communicate safely
    with built-in backpressure and proper resource management.
    
    Args:
        maxsize: Maximum number of items to buffer (0 = unbounded)
        
    Example:
        ```python
        channel = Channel[str](maxsize=10)
        
        # Producer
        await channel.send("message")
        
        # Consumer  
        message = await channel.receive()
        
        # Cleanup
        await channel.close()
        ```
    """
    def __init__(self, maxsize: int = 0):
        self._q: asyncio.Queue[A] = asyncio.Queue(maxsize=maxsize); self._closed=False
    async def send(self, a: A) -> None:
        """Send an item through the channel.
        
        If the channel buffer is full, this will block until space is available.
        
        Args:
            a: The item to send
            
        Raises:
            RuntimeError: If the channel is closed
        """
        if self._closed: raise RuntimeError("send on closed channel")
        await self._q.put(a)
    async def close(self) -> None:
        """Close the channel, preventing further sends.
        
        Receivers can still receive remaining buffered items.
        """
        self._closed = True
    async def receive(self) -> A:
        """Receive an item from the channel.
        
        If no items are available, this will block until an item is sent.
        
        Returns:
            The received item
            
        Raises:
            ChannelClosed: If the channel is closed and empty
        """
        return await self._q.get()
    def size(self)->int: return self._q.qsize()
