from __future__ import annotations
from typing import Any, Dict, TypeVar

A = TypeVar("A")

class Context:
    """Type-safe service container for dependency injection.
    
    Context holds services that effects can access. Services are stored by type,
    providing compile-time safety and runtime efficiency.
    
    Args:
        values: Optional initial services dictionary
        
    Example:
        ```python
        # Create context with services
        ctx = (Context()
               .with_service(Logger, Logger())
               .with_service(Database, Database("postgresql://...")))
        
        # Access services in effects
        logger = ctx.get(Logger)
        db = ctx.get(Database)
        ```
    """
    def __init__(self, values: Dict[type, Any] | None = None): self._values = dict(values or {})
    def get(self, t: type[A]) -> A:
        """Get a service from the context by type.
        
        Args:
            t: The type of service to retrieve
            
        Returns:
            The service instance
            
        Raises:
            KeyError: If the service type is not available
            
        Example:
            ```python
            logger = ctx.get(Logger)
            database = ctx.get(Database)
            ```
        """
        if t not in self._values: raise KeyError(f"Missing service: {t}")
        return self._values[t]
    def add(self, t: type[A], v: A) -> "Context":
        """Add a service to the context.
        
        Returns a new Context with the added service. The original context
        is unchanged (contexts are immutable).
        
        Args:
            t: The type of the service
            v: The service instance
            
        Returns:
            New context containing the added service
            
        Example:
            ```python
            new_ctx = ctx.add(Logger, Logger())
            # or use the more convenient alias:
            new_ctx = ctx.with_service(Logger, Logger())
            ```
        """
        c = dict(self._values); c[t] = v; return Context(c)
    
    def with_service(self, t: type[A], v: A) -> "Context":
        """Convenient alias for add() - add a service to the context.
        
        Args:
            t: The type of the service
            v: The service instance
            
        Returns:
            New context containing the added service
        """
        return self.add(t, v)
