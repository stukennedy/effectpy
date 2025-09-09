from __future__ import annotations
from typing import Awaitable, Callable, Any
from .context import Context
from .scope import Scope

class Layer:
    """Composable resource builder for dependency injection.
    
    A Layer describes how to build services into a Context and how to clean them up.
    Layers can be composed sequentially (+) for dependencies or in parallel (|)
    for independent services.
    
    Args:
        acquire: Function to build services into a context
        release: Function to clean up services
        
    Example:
        ```python
        # Define a database layer
        def build_db(ctx: Context, memo: dict) -> Context:
            db = Database("postgresql://...")
            return ctx.with_service(Database, db)
            
        def teardown_db(ctx: Context, memo: dict) -> None:
            db = ctx.get(Database)
            await db.close()
            
        DatabaseLayer = Layer(build_db, teardown_db)
        ```
    """
    def __init__(self, acquire: Callable[[Context, dict], Awaitable[Context]], release: Callable[[Context, dict], Awaitable[None]]):
        self._acquire = acquire; self._release = release

    async def build(self, parent: Context) -> Context:
        """Build this layer's services into a new context.
        
        Args:
            parent: The parent context to extend
            
        Returns:
            New context with this layer's services added
        """
        return await self._acquire(parent, {})
    async def build_memo(self, parent: Context, memo: dict) -> Context: return await self._acquire(parent, memo)

    async def build_scoped(self, parent: Context, scope: Scope, memo: dict | None = None) -> Context:
        """Build this layer and register cleanup with a scope.
        
        The layer is built and a finalizer is added to the scope to ensure
        proper cleanup when the scope closes.
        
        Args:
            parent: The parent context to extend
            scope: The scope to register cleanup with
            memo: Optional memoization dictionary for complex layers
            
        Returns:
            New context with this layer's services and guaranteed cleanup
            
        Example:
            ```python
            scope = Scope()
            env = await DatabaseLayer.build_scoped(Context(), scope)
            # Use database...
            await scope.close()  # Database automatically cleaned up
            ```
        """
        memo = memo or {}
        ctx = await self._acquire(parent, memo)
        async def fin(): await self._release(ctx, memo)
        await scope.add_finalizer(fin)
        return ctx

    async def teardown(self, ctx: Context) -> None: await self._release(ctx, {})
    async def teardown_memo(self, ctx: Context, memo: dict) -> None: await self._release(ctx, memo)

    def __add__(self, other: "Layer") -> "Layer":
        """Sequential layer composition - build dependencies first.
        
        The left layer is built first, then the right layer is built with
        access to the left layer's services. Use this when the right layer
        depends on services from the left layer.
        
        Args:
            other: Layer to compose sequentially after this one
            
        Returns:
            New layer representing sequential composition
            
        Example:
            ```python
            # Database depends on Logger
            AppLayer = LoggerLayer + DatabaseLayer
            ```
        """
        async def acq(parent: Context, memo: dict):
            left = await self.build_memo(parent, memo)
            try:
                right = await other.build_memo(left, memo)
            except BaseException:
                # Teardown left if right acquisition fails
                try:
                    await self.teardown_memo(left, memo)
                finally:
                    raise
            return right
        async def rel(ctx: Context, memo: dict):
            await other.teardown_memo(ctx, memo); await self.teardown_memo(ctx, memo)
        return Layer(acq, rel)

    def __or__(self, other: "Layer") -> "Layer":
        """Parallel layer composition - build services concurrently.
        
        Both layers are built concurrently. Use this when the layers are
        independent and don't depend on each other's services.
        
        Args:
            other: Layer to compose in parallel with this one
            
        Returns:
            New layer representing parallel composition
            
        Example:
            ```python
            # Logger and Metrics are independent
            ObservabilityLayer = LoggerLayer | MetricsLayer
            ```
        """
        import asyncio
        async def acq(parent: Context, memo: dict):
            res = await asyncio.gather(self.build_memo(parent, memo), other.build_memo(parent, memo), return_exceptions=True)
            c1, c2 = res
            if isinstance(c1, BaseException) or isinstance(c2, BaseException):
                # Teardown whichever succeeded
                if not isinstance(c1, BaseException):
                    try: await self.teardown_memo(c1, memo)  # type: ignore[arg-type]
                    except Exception: pass
                if not isinstance(c2, BaseException):
                    try: await other.teardown_memo(c2, memo)  # type: ignore[arg-type]
                    except Exception: pass
                # Raise first error
                first_err = c1 if isinstance(c1, BaseException) else c2  # type: ignore[assignment]
                raise first_err  # type: ignore[misc]
            merged = c1
            for k, v in c2._values.items():
                merged = merged.add(k, v)
            return merged
        async def rel(ctx: Context, memo: dict):
            import asyncio; await asyncio.gather(self.teardown_memo(ctx, memo), other.teardown_memo(ctx, memo))
        return Layer(acq, rel)

def from_resource(t: type, mk: Callable[[Context], Awaitable[Any]], close: Callable[[Any], Awaitable[None]]) -> Layer:
    """Create a Layer from simple build and teardown functions.
    
    This is a convenient helper for creating layers when you have simple
    functions to create and destroy a resource.
    
    Args:
        t: The service type to provide
        mk: Function to create the service instance
        close: Function to clean up the service instance
        
    Returns:
        A new Layer that manages the resource
        
    Example:
        ```python
        class Database:
            def __init__(self, url: str): ...
            async def close(self): ...
        
        DatabaseLayer = from_resource(
            Database,
            lambda ctx: Database("postgresql://localhost:5432/db"),
            lambda db: db.close()
        )
        ```
    """
    async def acquire(parent: Context, memo: dict):
        key = ('resource', t)
        if key in memo: inst = memo[key]
        else:
            inst = await mk(parent); memo[key] = inst
        return parent.add(t, inst)
    async def release(ctx: Context, memo: dict):
        key = ('resource', t)
        inst = memo.get(key) or ctx.get(t)
        await close(inst)
    return Layer(acquire, release)
