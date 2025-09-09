from __future__ import annotations
from typing import Awaitable, Callable, List

class Scope:
    """Resource lifecycle manager with guaranteed cleanup.
    
    Scope ensures that resources are cleaned up in LIFO order (Last In, First Out)
    even when exceptions occur. This is essential for safe resource management
    in async applications.
    
    Example:
        ```python
        scope = Scope()
        
        # Add resources to scope
        db = Database("postgresql://...")
        scope.add_finalizer(db.close)
        
        cache = Cache("redis://...")
        scope.add_finalizer(cache.close)
        
        try:
            # Use resources...
            pass
        finally:
            await scope.close()  # Closes cache, then db (LIFO order)
        ```
    """
    def __init__(self):
        self._finalizers: List[Callable[[], Awaitable[None]]] = []
        self._closed = False

    async def add_finalizer(self, fin: Callable[[], Awaitable[None]]) -> None:
        """Add a cleanup function to be called when the scope closes.
        
        Finalizers are called in LIFO order (reverse of addition order).
        If the scope is already closed, the finalizer is executed immediately.
        
        Args:
            fin: Async function to call during cleanup
            
        Example:
            ```python
            scope = Scope()
            
            # Add cleanup functions
            scope.add_finalizer(lambda: database.close())
            scope.add_finalizer(lambda: cache.disconnect())
            
            # Later...
            await scope.close()  # Calls cache.disconnect(), then database.close()
            ```
        """
        if self._closed: await fin()
        else: self._finalizers.append(fin)

    async def close(self) -> None:
        """Close the scope and run all finalizers in LIFO order.
        
        Finalizers are executed in reverse order of addition. Even if some
        finalizers fail, all remaining finalizers will still be executed.
        The scope becomes closed and cannot accept new finalizers.
        
        Raises:
            No exceptions - finalizer failures are swallowed to ensure
            all cleanup attempts are made.
            
        Example:
            ```python
            scope = Scope()
            scope.add_finalizer(cleanup1)
            scope.add_finalizer(cleanup2)
            
            await scope.close()  # Runs cleanup2, then cleanup1
            ```
        """
        if self._closed: return
        self._closed = True
        while self._finalizers:
            fin = self._finalizers.pop()
            try: await fin()
            except Exception: pass
