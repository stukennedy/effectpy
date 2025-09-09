# Layers & Scope

Resource management is one of the hardest problems in async programming. effectpy solves this with two key abstractions:

- **`Layer`**: Describes how to build and teardown services
- **`Scope`**: Guarantees resources are cleaned up in the correct order (LIFO)

Together, they provide **guaranteed resource safety** - no more leaked connections, forgotten cleanup, or race conditions during shutdown.

## The Problem

Traditional async Python resource management is error-prone:

```python
# ❌ Easy to forget cleanup, or cleanup in wrong order
async def risky_approach():
    db = Database("postgresql://...")
    cache = Cache("redis://...")
    logger = Logger()
    
    try:
        # Do work...
        pass
    finally:
        # What if this fails? What if we forget one?
        # What's the right order?
        await db.close()
        await cache.close() 
        await logger.close()
```

Problems with this approach:
- **Cleanup order matters** - close things in reverse of creation
- **Exception safety** - cleanup must happen even if operations fail
- **Complex dependencies** - some resources depend on others
- **Easy to forget** - manual cleanup is error-prone

## The effectpy Solution

```python
# ✅ Guaranteed cleanup in correct order
import asyncio
from effectpy import *

async def safe_approach():
    scope = Scope()
    
    # Build environment with multiple resources
    env = await (DatabaseLayer | CacheLayer | LoggerLayer).build_scoped(Context(), scope)
    
    # Use resources safely
    db = env.get(Database)
    result = await db.query("SELECT 1")
    print(f"Result: {result}")
    
    # Guaranteed cleanup in reverse order, even if exceptions occur
    await scope.close()  # Cache → Database → Logger (LIFO order)
```

## Context: Service Container

`Context` is a type-safe service container that holds your application's dependencies:

```python
from effectpy import *

class Logger:
    def log(self, msg: str):
        print(f"[LOG] {msg}")

class Database:
    def __init__(self, url: str):
        self.url = url
        print(f"Connected to {url}")

# Manual context building
ctx = (Context()
       .with_service(Logger, Logger())
       .with_service(Database, Database("postgresql://localhost")))

# Type-safe retrieval
logger = ctx.get(Logger)  # Returns Logger instance
db = ctx.get(Database)    # Returns Database instance

logger.log("Hello from context!")
```

### Context Features

```python
# Check if service exists
if ctx.has(Logger):
    logger = ctx.get(Logger)

# Get with default
config = ctx.get_or_else(Config, Config.default())

# Get optional (returns None if not found)
maybe_cache = ctx.get_optional(Cache)

# Context is immutable - operations return new instances
new_ctx = ctx.with_service(Metrics, MetricsRegistry())
```

## Scope: Resource Lifecycle Manager

`Scope` manages the lifecycle of resources with guaranteed cleanup:

```python
import asyncio
from effectpy import *

class Resource:
    def __init__(self, name: str):
        self.name = name
        print(f"🔧 Created resource: {name}")
    
    async def close(self):
        print(f"🔧 Closed resource: {self.name}")

async def scope_example():
    scope = Scope()
    
    # Add resources to scope
    r1 = Resource("Database")
    r2 = Resource("Cache") 
    r3 = Resource("Logger")
    
    scope.add_finalizer(r1.close)
    scope.add_finalizer(r2.close)
    scope.add_finalizer(r3.close)
    
    print("Doing work...")
    
    # Cleanup happens in LIFO order (reverse of addition)
    await scope.close()  # Logger → Cache → Database

asyncio.run(scope_example())
```

Output:
```
🔧 Created resource: Database
🔧 Created resource: Cache
🔧 Created resource: Logger
Doing work...
🔧 Closed resource: Logger
🔧 Closed resource: Cache  
🔧 Closed resource: Database
```

### Scope Features

```python
# Different ways to add cleanup
scope.add_finalizer(resource.close)              # Async function
scope.add_finalizer(lambda: print("cleanup"))    # Sync function
scope.add_sync_finalizer(file.close)            # Explicitly sync

# Nested scopes
parent_scope = Scope()
child_scope = parent_scope.child()
await child_scope.close()  # Child cleaned up first
await parent_scope.close()  # Then parent

# Exception safety
try:
    # Even if this fails...
    raise ValueError("Something went wrong!")
finally:
    await scope.close()  # Cleanup still happens
```

## Layer: Service Builders

`Layer` describes how to construct and teardown services. Layers are composable and guarantee proper resource management:

### Creating Layers

```python
import asyncio
from effectpy import *

class Database:
    def __init__(self, url: str):
        self.url = url
        print(f"🔌 Connected to database: {url}")
    
    async def close(self):
        print(f"🔌 Closed database: {self.url}")

# Simple layer using from_resource
DatabaseLayer = from_resource(
    service_type=Database,
    build=lambda ctx: Database("postgresql://localhost:5432/myapp"),
    teardown=lambda db: db.close()
)

# More complex layer with dependencies
class Cache:
    def __init__(self, url: str, logger: Logger):
        self.url = url
        self.logger = logger
        logger.log(f"Cache connecting to {url}")
    
    async def close(self):
        self.logger.log(f"Cache closing {self.url}")

def CacheLayer(redis_url: str = "redis://localhost") -> Layer:
    async def build(ctx: Context) -> Context:
        logger = ctx.get(Logger)  # Depends on Logger
        cache = Cache(redis_url, logger)
        return ctx.with_service(Cache, cache)
    
    async def teardown(ctx: Context) -> None:
        cache = ctx.get(Cache)
        await cache.close()
    
    return Layer(build=build, teardown=teardown)
```

### Layer Composition

Layers can be composed in two ways:

#### Sequential Composition (`+`)

Sequential composition builds layers one after another. Later layers can depend on earlier ones:

```python
# Sequential: Logger first, then Database (which can use Logger)
sequential_layer = LoggerLayer + DatabaseLayer
```

#### Parallel Composition (`|`)

Parallel composition builds layers concurrently. They cannot depend on each other:

```python  
# Parallel: All three built concurrently
parallel_layer = LoggerLayer | MetricsLayer | TracerLayer

# Mixed: Logger first, then others in parallel
mixed_layer = LoggerLayer + (MetricsLayer | TracerLayer)
```

### Using Layers

```python
async def layer_example():
    scope = Scope()
    base = Context()
    
    # Build environment
    env = await DatabaseLayer.build_scoped(base, scope)
    
    # Use the service
    db = env.get(Database)
    result = await db.query("SELECT 1")
    print(f"Query result: {result}")
    
    # Guaranteed cleanup
    await scope.close()

# Or use the convenience method
async def convenient_layer_example():
    async with DatabaseLayer.scoped(Context()) as env:
        db = env.get(Database)
        result = await db.query("SELECT 1")
        print(f"Query result: {result}")
    # Automatic cleanup when exiting context manager
```

## Real-World Example

Here's a comprehensive example showing layers, scopes, and effects working together:

```python
import asyncio
from effectpy import *

# Service definitions
class Config:
    def __init__(self):
        self.db_url = "postgresql://localhost:5432/myapp"
        self.redis_url = "redis://localhost:6379"
        self.log_level = "INFO"

class Logger:
    def __init__(self, level: str):
        self.level = level
        print(f"📝 Logger initialized (level: {level})")
    
    def info(self, msg: str):
        print(f"[INFO] {msg}")
    
    def error(self, msg: str):
        print(f"[ERROR] {msg}")
    
    async def close(self):
        print("📝 Logger closed")

class Database:
    def __init__(self, url: str, logger: Logger):
        self.url = url
        self.logger = logger
        logger.info(f"Database connecting to {url}")
    
    async def query(self, sql: str) -> list:
        await asyncio.sleep(0.1)  # Simulate query
        self.logger.info(f"Executed: {sql}")
        return [{"id": 1, "name": "Alice"}]
    
    async def close(self):
        self.logger.info("Database connection closed")

class Cache:
    def __init__(self, url: str, logger: Logger):
        self.url = url
        self.logger = logger
        logger.info(f"Cache connecting to {url}")
        self._data = {}
    
    def get(self, key: str) -> str | None:
        value = self._data.get(key)
        self.logger.info(f"Cache GET {key}: {'HIT' if value else 'MISS'}")
        return value
    
    def set(self, key: str, value: str):
        self._data[key] = value
        self.logger.info(f"Cache SET {key}")
    
    async def close(self):
        self.logger.info("Cache connection closed")

# Layer definitions
ConfigLayer = from_resource(
    Config,
    build=lambda ctx: Config(),
    teardown=lambda config: None  # No cleanup needed
)

def LoggerLayer() -> Layer:
    async def build(ctx: Context) -> Context:
        config = ctx.get(Config)
        logger = Logger(config.log_level)
        return ctx.with_service(Logger, logger)
    
    async def teardown(ctx: Context) -> None:
        logger = ctx.get(Logger)
        await logger.close()
    
    return Layer(build=build, teardown=teardown)

def DatabaseLayer() -> Layer:
    async def build(ctx: Context) -> Context:
        config = ctx.get(Config)
        logger = ctx.get(Logger)
        database = Database(config.db_url, logger)
        return ctx.with_service(Database, database)
    
    async def teardown(ctx: Context) -> None:
        database = ctx.get(Database)
        await database.close()
    
    return Layer(build=build, teardown=teardown)

def CacheLayer() -> Layer:
    async def build(ctx: Context) -> Context:
        config = ctx.get(Config)
        logger = ctx.get(Logger)
        cache = Cache(config.redis_url, logger)
        return ctx.with_service(Cache, cache)
    
    async def teardown(ctx: Context) -> None:
        cache = ctx.get(Cache)
        await cache.close()
    
    return Layer(build=build, teardown=teardown)

# Application layer with dependencies
AppLayer = ConfigLayer + LoggerLayer() + (DatabaseLayer() | CacheLayer())

# Business logic using effects
def fetch_user_with_cache(user_id: int) -> Effect[Database | Cache | Logger, str, dict]:
    async def impl(ctx: Context):
        db = ctx.get(Database)
        cache = ctx.get(Cache)
        logger = ctx.get(Logger)
        
        # Check cache first
        cache_key = f"user:{user_id}"
        cached = cache.get(cache_key)
        
        if cached:
            return {"id": user_id, "name": cached, "from_cache": True}
        
        # Fetch from database
        try:
            users = await db.query(f"SELECT * FROM users WHERE id = {user_id}")
            if not users:
                return {"error": "User not found"}
            
            user = users[0]
            cache.set(cache_key, user["name"])
            return {**user, "from_cache": False}
        
        except Exception as e:
            logger.error(f"Database error: {e}")
            return {"error": "Database unavailable"}
    
    return Effect(impl)

async def main():
    scope = Scope()
    
    # Build complete application environment
    env = await AppLayer.build_scoped(Context(), scope)
    
    # Create instrumented effect
    fetch_effect = instrument(
        "user.fetch",
        fetch_user_with_cache(42),
        tags={"operation": "user_fetch", "user_id": 42}
    )
    
    # First call (cache miss)
    result1 = await fetch_effect._run(env)
    print(f"First call: {result1}")
    
    # Second call (cache hit)
    result2 = await fetch_effect._run(env)
    print(f"Second call: {result2}")
    
    # Guaranteed cleanup in correct order
    print("\nCleaning up...")
    await scope.close()

if __name__ == "__main__":
    asyncio.run(main())
```

Output:
```
📝 Logger initialized (level: INFO)
[INFO] Database connecting to postgresql://localhost:5432/myapp
[INFO] Cache connecting to redis://localhost:6379
[INFO] Executed: SELECT * FROM users WHERE id = 42
[INFO] Cache SET user:42
First call: {'id': 1, 'name': 'Alice', 'from_cache': False}
[INFO] Cache GET user:42: HIT
Second call: {'id': 1, 'name': 'Alice', 'from_cache': True}

Cleaning up...
[INFO] Cache connection closed
[INFO] Database connection closed
📝 Logger closed
```

## Built-in Layers

effectpy includes several built-in layers for common services:

### Observability Layers

```python
# Logging
logger_env = await LoggerLayer.build_scoped(Context(), scope)

# Metrics
metrics_env = await MetricsLayer.build_scoped(Context(), scope)

# Tracing
tracer_env = await TracerLayer.build_scoped(Context(), scope)

# All observability services
observability = LoggerLayer | MetricsLayer | TracerLayer
obs_env = await observability.build_scoped(Context(), scope)
```

### Clock Layers

```python
# Real clock
real_clock_env = await ClockLayer.build_scoped(Context(), scope)

# Test clock for deterministic testing
test_clock = TestClock()
test_env = await TestClockLayer(test_clock).build_scoped(Context(), scope)
```

## Best Practices

### 1. Always Use Scopes for Resources

```python
# ✅ Good: Always use Scope
async def good_resource_management():
    scope = Scope()
    env = await DatabaseLayer.build_scoped(Context(), scope)
    
    try:
        # Use resources...
        pass
    finally:
        await scope.close()  # Guaranteed cleanup

# ❌ Avoid: Manual resource management
async def avoid_manual_management():
    db = Database("postgresql://...")
    try:
        # Use database...
        pass
    finally:
        await db.close()  # Easy to forget, no ordering guarantees
```

### 2. Compose Layers Thoughtfully

```python
# Dependencies: Config → Logger → (Database | Cache)
# This ensures Logger is available for both Database and Cache
app_layer = ConfigLayer + LoggerLayer() + (DatabaseLayer() | CacheLayer())

# ❌ Wrong: Database needs Logger but they're built in parallel
wrong_layer = LoggerLayer() | DatabaseLayer()  # Race condition!
```

### 3. Use Layer Composition

```python
# ✅ Good: Compose small, focused layers
auth_layer = ConfigLayer + LoggerLayer() + DatabaseLayer() + AuthServiceLayer()
metrics_layer = MetricsLayer | TracerLayer
app_layer = auth_layer + metrics_layer

# ❌ Avoid: Monolithic layers
giant_layer = EverythingLayer()  # Hard to test, debug, and reuse
```

### 4. Handle Layer Failures Gracefully

```python
async def robust_layer_usage():
    scope = Scope()
    
    try:
        env = await AppLayer.build_scoped(Context(), scope)
        # Use environment...
        
    except Exception as e:
        print(f"Failed to build environment: {e}")
        # scope.close() still happens in finally
        
    finally:
        await scope.close()  # Always cleanup
```

## Testing with Layers

Layers make testing easy by allowing dependency injection:

```python
# Production layers
ProductionLayer = ConfigLayer + LoggerLayer() + DatabaseLayer()

# Test layers with mocks
class MockDatabase:
    async def query(self, sql: str) -> list:
        return [{"id": 1, "name": "Test User"}]
    async def close(self): pass

TestDatabaseLayer = from_resource(
    Database,
    build=lambda ctx: MockDatabase(),
    teardown=lambda db: db.close()
)

TestLayer = ConfigLayer + LoggerLayer() + TestDatabaseLayer

# Same business logic, different environment
async def test_user_service():
    scope = Scope()
    test_env = await TestLayer.build_scoped(Context(), scope)
    
    result = await fetch_user_with_cache(1)._run(test_env)
    assert result["name"] == "Test User"
    
    await scope.close()
```

## What's Next?

- **→ [Effects](effects.md)** - Working with effectpy computations
- **→ [Runtime & Fibers](runtime_fibers.md)** - Concurrent execution
- **→ [Services Guide](../guides/services_env.md)** - Dependency injection patterns
- **→ [Context & Scope API](../reference/context_scope.md)** - Complete API reference

