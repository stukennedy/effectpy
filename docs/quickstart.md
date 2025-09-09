# Quick Start

This guide walks you through the core concepts of effectpy with practical examples. In just a few minutes, you'll understand how to build robust async applications with guaranteed resource safety and rich error handling.

## Your First Effect

Let's start with the simplest possible effectpy program:

```python title="hello_effect.py"
import asyncio
from effectpy import *

async def main():
    # Create a simple effect that succeeds with a value
    hello_effect = succeed("Hello, effectpy!")
    
    # Run the effect
    result = await hello_effect._run(Context())
    print(result)  # Output: Hello, effectpy!

asyncio.run(main())
```

**Key concepts:**
- **Effect**: A computation that may require resources, fail, or succeed
- **Context**: The environment where effects run (starts empty)
- `succeed()`: Creates an effect that immediately succeeds with a value

## Effect Composition

Effects shine when you compose them. Let's build a computation pipeline:

```python title="composition.py"
import asyncio
from effectpy import *

async def main():
    # Chain operations with map and flat_map
    computation = (
        succeed(10)                           # Start with 10
        .map(lambda x: x * 2)                # Multiply by 2 → 20
        .flat_map(lambda x: succeed(x + 5))  # Add 5 → 25
        .map(lambda x: f"Result: {x}")       # Format → "Result: 25"
    )
    
    result = await computation._run(Context())
    print(result)  # Output: Result: 25

asyncio.run(main())
```

**Key concepts:**
- `.map()`: Transform the success value
- `.flat_map()`: Chain effects together
- Effects are lazy - nothing runs until `._run()` is called

## Error Handling

effectpy provides structured error handling with rich failure information:

```python title="error_handling.py"
import asyncio
from effectpy import *

async def divide(x: int, y: int) -> Effect[Any, str, float]:
    if y == 0:
        return fail("Division by zero!")
    return succeed(x / y)

async def main():
    # Successful computation  
    success = await divide(10, 2)._run(Context())
    print(f"Success: {success}")  # Output: Success: 5.0
    
    # Handle errors gracefully
    safe_division = (
        divide(10, 0)
        .catch_all(lambda error: succeed(f"Error handled: {error}"))
    )
    
    result = await safe_division._run(Context())
    print(result)  # Output: Error handled: Division by zero!

asyncio.run(main())
```

**Key concepts:**
- `fail()`: Create an effect that fails with an error
- `.catch_all()`: Handle and recover from errors
- Type safety: `Effect[R, E, A]` where E is the error type

## Resource Management

Real applications need resources like database connections, files, or HTTP clients. effectpy ensures they're always cleaned up:

```python title="resources.py"
import asyncio
from effectpy import *

class Database:
    def __init__(self, url: str):
        self.url = url
        print(f"🔌 Connected to database: {url}")
    
    async def query(self, sql: str) -> str:
        await asyncio.sleep(0.1)  # Simulate DB work
        return f"Result for '{sql}'"
    
    async def close(self):
        print(f"🔌 Closed database connection: {self.url}")

# Define a resource layer
DatabaseLayer = from_resource(
    Database,
    build=lambda ctx: Database("postgresql://localhost:5432/mydb"),
    teardown=lambda db: db.close()
)

async def main():
    scope = Scope()
    
    # Build environment with database
    env = await DatabaseLayer.build_scoped(Context(), scope)
    db = env.get(Database)
    
    # Use the database
    result = await db.query("SELECT * FROM users")
    print(f"Query result: {result}")
    
    # Guaranteed cleanup - even if exceptions occur!
    await scope.close()

asyncio.run(main())
```

Output:
```
🔌 Connected to database: postgresql://localhost:5432/mydb
Query result: Result for 'SELECT * FROM users'
🔌 Closed database connection: postgresql://localhost:5432/mydb
```

**Key concepts:**
- **Scope**: Manages resource lifecycles with guaranteed cleanup
- **Layer**: Defines how to build and teardown resources  
- `from_resource()`: Helper to create layers from simple build/teardown functions

## Observability

effectpy includes built-in observability. Instrument any effect to get automatic logging, metrics, and tracing:

```python title="observability.py"
import asyncio
from effectpy import *

async def fetch_user(user_id: int) -> Effect[Any, str, dict]:
    await asyncio.sleep(0.1)  # Simulate network call
    if user_id <= 0:
        return fail("Invalid user ID")
    return succeed({"id": user_id, "name": f"User {user_id}"})

async def main():
    scope = Scope()
    
    # Set up observability layers
    env = await (LoggerLayer | MetricsLayer | TracerLayer).build_scoped(Context(), scope)
    
    # Instrument the effect
    instrumented = instrument(
        "user.fetch", 
        fetch_user(42),
        tags={"service": "user-api", "version": "1.0"}
    )
    
    result = await instrumented._run(env)
    print(f"User: {result}")
    
    await scope.close()

asyncio.run(main())
```

**Key concepts:**
- `instrument()`: Wraps effects with automatic observability
- **Tags**: Add metadata for filtering and grouping
- **Layers composition**: Use `|` to combine multiple layers

## Concurrent Operations

effectpy provides safe, structured concurrency primitives:

```python title="concurrency.py"
import asyncio
from effectpy import *

async def fetch_data(name: str, delay: float) -> Effect[Any, None, str]:
    await asyncio.sleep(delay)
    return succeed(f"Data from {name}")

async def main():
    # Run effects in parallel
    concurrent_effects = [
        fetch_data("API-1", 0.1),
        fetch_data("API-2", 0.2), 
        fetch_data("API-3", 0.15)
    ]
    
    # zip_par: run all and combine results
    all_results = await zip_par(*concurrent_effects)._run(Context())
    print(f"All results: {all_results}")
    
    # race: return first to complete
    first_result = await race(*concurrent_effects)._run(Context())
    print(f"First result: {first_result}")

asyncio.run(main())
```

**Key concepts:**
- `zip_par()`: Run effects concurrently, wait for all
- `race()`: Run effects concurrently, return first success
- Automatic cancellation of other operations

## Putting It All Together

Here's a complete example showing effectpy's power:

```python title="complete_example.py"
import asyncio
from effectpy import *

class APIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        print(f"🌐 API client connected to {base_url}")
    
    async def get(self, endpoint: str) -> dict:
        await asyncio.sleep(0.1)  # Simulate HTTP request
        return {"endpoint": endpoint, "data": f"Response from {endpoint}"}
    
    async def close(self):
        print("🌐 API client closed")

class Cache:
    def __init__(self):
        self._cache = {}
        print("💾 Cache initialized")
    
    def get(self, key: str) -> str | None:
        return self._cache.get(key)
    
    def set(self, key: str, value: str):
        self._cache[key] = value
    
    async def close(self):
        print("💾 Cache closed")

# Define resource layers
APILayer = from_resource(
    APIClient,
    lambda ctx: APIClient("https://api.example.com"),
    lambda client: client.close()
)

CacheLayer = from_resource(
    Cache,
    lambda ctx: Cache(),
    lambda cache: cache.close()
)

async def fetch_with_cache(endpoint: str) -> Effect[APIClient | Cache, str, dict]:
    def impl(ctx: Context) -> Effect[APIClient | Cache, str, dict]:
        cache = ctx.get(Cache)
        api = ctx.get(APIClient)
        
        # Check cache first
        cached = cache.get(endpoint)
        if cached:
            print(f"💾 Cache hit for {endpoint}")
            return succeed({"cached": True, "data": cached})
        
        # Fetch from API and cache result
        async def fetch_and_cache():
            print(f"🌐 Fetching {endpoint} from API")
            data = await api.get(endpoint)
            cache.set(endpoint, str(data))
            return data
        
        return from_async(fetch_and_cache)
    
    return Effect(lambda ctx: impl(ctx)._run(ctx))

async def main():
    scope = Scope()
    
    # Compose all layers
    env = await (
        LoggerLayer | 
        MetricsLayer | 
        APILayer | 
        CacheLayer
    ).build_scoped(Context(), scope)
    
    # Create instrumented effects
    fetch1 = instrument("api.fetch", fetch_with_cache("/users/1"), tags={"endpoint": "/users/1"})
    fetch2 = instrument("api.fetch", fetch_with_cache("/users/1"), tags={"endpoint": "/users/1"}) 
    
    # First call hits API
    result1 = await fetch1._run(env)
    print(f"Result 1: {result1}")
    
    # Second call hits cache
    result2 = await fetch2._run(env)
    print(f"Result 2: {result2}")
    
    # Guaranteed cleanup of all resources
    await scope.close()

asyncio.run(main())
```

Output:
```
🌐 API client connected to https://api.example.com
💾 Cache initialized
🌐 Fetching /users/1 from API
Result 1: {'endpoint': '/users/1', 'data': 'Response from /users/1'}
💾 Cache hit for /users/1
Result 2: {'cached': True, 'data': "{'endpoint': '/users/1', 'data': 'Response from /users/1'}"}
💾 Cache closed
🌐 API client closed
```

## Examples

effectpy includes comprehensive examples you can run immediately:

```bash
# Basic effects and composition
python -m examples.basic_effects

# Resource management with layers
python -m examples.layers_resource_safety  

# Scoped layer provision
python -m examples.provide_layer_example

# Concurrent fibers
python -m examples.fibers_concurrency

# Streaming pipelines
python -m examples.pipelines_parallel

# AnyIO runtime (requires anyio)
python -m examples.anyio_runtime_example

# OTLP exporters (requires aiohttp)  
python -m examples.exporters_demo
```

## What's Next?

Now that you understand the basics, dive deeper into effectpy:

### 💡 **Core Concepts**
Learn about Effects, Causes, Layers, and Scopes in detail

**→ [Effects](concepts/effects.md)**  
**→ [Layers & Scope](concepts/layers_scope.md)**

### 🏁 **Concurrency**  
Master structured concurrency, fibers, and parallel operations

**→ [Concurrency Guide](guides/concurrency.md)**  
**→ [Runtime & Fibers](concepts/runtime_fibers.md)**

### 🔧 **Streaming**
Build data processing pipelines with streams and channels

**→ [Streams & Channels](concepts/streams_channels.md)**

### 👁️ **Observability**
Add logging, metrics, and tracing to your applications

**→ [Observability](concepts/observability.md)**

