# Effects

Effects are the heart of effectpy. An `Effect[R, E, A]` represents an async computation that:

- **Requires environment `R`** (services from `Context`)  
- **May fail with error `E`**
- **Succeeds with value `A`**

Effects are **lazy** - they describe computations but don't execute until you call `._run(context)`.

## The Effect Type

```python
Effect[R, E, A]
#      ^  ^  ^
#      |  |  |
#      |  |  +-- Success type (what you get on success)
#      |  +----- Error type (what you get on failure)
#      +-------- Environment type (what services you need)
```

### Common Effect Types

```python
from effectpy import *

# Simple success - no environment needed, can't fail
simple: Effect[Any, None, str] = succeed("Hello!")

# May fail with string error
fallible: Effect[Any, str, int] = fail("Something went wrong")

# Needs Database service, may fail with DbError
database_effect: Effect[Database, DbError, User] = ...
```

## Creating Effects

### Basic Constructors

```python
import asyncio
from effectpy import *

# Always succeeds
success_effect = succeed(42)

# Always fails  
failure_effect = fail("Error message")

# From async function
async def fetch_data():
    await asyncio.sleep(0.1)
    return "data"

async_effect = from_async(fetch_data)

# From sync function with error handling
def risky_operation():
    if random() < 0.5:
        raise ValueError("Random failure!")
    return "success"

safe_effect = attempt(risky_operation)
```

### Error Handling

effectpy uses **structured errors** through the `Cause` type, which can represent:

- **Failures**: Expected errors from your business logic
- **Defects**: Unexpected exceptions (bugs)
- **Interruptions**: Cancellation signals
- **Combinations**: Multiple errors composed together

```python
import asyncio
from effectpy import *

async def divide(x: int, y: int) -> Effect[Any, str, float]:
    if y == 0:
        return fail("Division by zero")
    return succeed(x / y)

async def main():
    # Handle specific errors
    safe_divide = (
        divide(10, 0)
        .catch_all(lambda error: succeed(f"Handled: {error}"))
    )
    
    result = await safe_divide._run(Context())
    print(result)  # "Handled: Division by zero"

    # Let errors bubble up
    try:
        await divide(10, 0)._run(Context())
    except Failure as f:
        print(f"Caught failure: {f.error}")  # "Caught failure: Division by zero"

asyncio.run(main())
```

## Effect Composition

### Sequential Composition

```python
from effectpy import *

# Chain operations with map
pipeline = (
    succeed(5)
    .map(lambda x: x * 2)      # 10
    .map(lambda x: x + 3)      # 13  
    .map(str)                  # "13"
)

# Chain effects with flat_map
def fetch_user(id: int) -> Effect[Any, str, dict]:
    if id <= 0:
        return fail("Invalid ID")
    return succeed({"id": id, "name": f"User {id}"})

def fetch_posts(user: dict) -> Effect[Any, str, list]:
    return succeed([f"Post by {user['name']}", "Another post"])

user_with_posts = (
    fetch_user(42)
    .flat_map(lambda user: fetch_posts(user).map(lambda posts: {"user": user, "posts": posts}))
)
```

### Parallel Composition

```python
import asyncio
from effectpy import *

async def fetch_data(name: str, delay: float) -> Effect[Any, None, str]:
    await asyncio.sleep(delay)
    return succeed(f"Data from {name}")

async def main():
    effects = [
        fetch_data("Service A", 0.1),
        fetch_data("Service B", 0.2),
        fetch_data("Service C", 0.15)
    ]
    
    # Run all in parallel, wait for all to complete
    all_results = await zip_par(*effects)._run(Context())
    print(f"All: {all_results}")
    
    # Race - return first to complete
    winner = await race(*effects)._run(Context())  
    print(f"Winner: {winner}")
    
    # Run in parallel but collect results individually
    results = await for_each_par(effects, lambda effect: effect)._run(Context())
    print(f"Each: {results}")

asyncio.run(main())
```

## Environment and Services

Effects can require services from the environment:

```python
from effectpy import *

class Logger:
    def log(self, msg: str):
        print(f"[LOG] {msg}")

class Database:
    async def query(self, sql: str) -> list:
        return [{"id": 1, "name": "Alice"}]

# Effect that needs both Logger and Database
def fetch_users() -> Effect[Logger | Database, str, list]:
    async def impl(ctx: Context):
        logger = ctx.get(Logger)
        db = ctx.get(Database)
        
        logger.log("Fetching users...")
        users = await db.query("SELECT * FROM users")
        logger.log(f"Found {len(users)} users")
        return users
    
    return Effect(impl)

# Usage
async def main():
    # Build environment
    ctx = Context().with_service(Logger, Logger()).with_service(Database, Database())
    
    users = await fetch_users()._run(ctx)
    print(users)

asyncio.run(main())
```

## Error Recovery Patterns

### Multiple Recovery Strategies

```python
from effectpy import *

def unreliable_service() -> Effect[Any, str, str]:
    import random
    if random.random() < 0.7:
        return fail("Service unavailable")
    return succeed("Service response")

# Try multiple strategies
recovery_effect = (
    unreliable_service()
    .catch_all(lambda _: unreliable_service())  # Retry once
    .catch_all(lambda _: succeed("Fallback response"))  # Use fallback
    .catch_all(lambda err: fail(f"All strategies failed: {err}"))  # Final error
)
```

### Cause Analysis

```python
from effectpy import *

async def analyze_failure():
    try:
        await fail("Business error")._run(Context())
    except Failure as f:
        cause = f.cause or Cause.fail(f.error)
        print("Failure analysis:")
        print(cause.render())
        
        # Check cause type
        if cause.kind == 'fail':
            print(f"Business error: {cause.error}")
        elif cause.kind == 'die': 
            print(f"Defect: {cause.defect}")
        elif cause.kind == 'interrupt':
            print("Operation was cancelled")

asyncio.run(analyze_failure())
```

## Resource Management

Effects integrate with `Scope` for guaranteed resource cleanup:

```python
import asyncio
from effectpy import *

class Connection:
    def __init__(self, url: str):
        self.url = url
        print(f"🔌 Connected to {url}")
    
    async def query(self, sql: str) -> str:
        await asyncio.sleep(0.1)
        return f"Result: {sql}"
    
    async def close(self):
        print(f"🔌 Closed connection to {self.url}")

def with_connection(url: str) -> Effect[Any, str, Connection]:
    return acquire_release(
        acquire=from_async(lambda: Connection(url)),
        release=lambda conn: from_async(conn.close)
    )

async def main():
    scope = Scope()
    
    # Resource is guaranteed to be cleaned up
    connection_effect = (
        with_connection("postgresql://localhost:5432/db")
        .flat_map(lambda conn: from_async(lambda: conn.query("SELECT 1")))
    )
    
    result = await connection_effect._run_scoped(Context(), scope)
    print(f"Query result: {result}")
    
    await scope.close()  # Connection automatically closed here

asyncio.run(main())
```

## Advanced Patterns

### Effect Annotations

Add metadata for debugging and observability:

```python
from effectpy import *

annotated_effect = (
    succeed(42)
    .map(lambda x: x * 2)
    .annotate("After doubling")
    .map(lambda x: x + 1) 
    .annotate("After incrementing")
)
```

### Conditional Effects  

```python
from effectpy import *

def conditional_logic(use_cache: bool) -> Effect[Any, str, str]:
    if use_cache:
        return succeed("Cached result")
    else:
        return from_async(lambda: asyncio.sleep(0.1)).flat_map(lambda _: succeed("Fresh result"))

# Or using Effect.when/unless
cached_effect = Effect.when(
    condition=True,
    effect=succeed("From cache"),
    default=succeed("Default value")
)
```

### Effect Transformations

```python
from effectpy import *

# Map errors to different types
string_to_int_error = (
    fail("Not a number")
    .map_error(lambda s: ValueError(s))  # str -> ValueError
)

# Ignore success value
just_for_effects = (
    succeed("Important side effect happened")
    .as_unit()  # Effect[R, E, None]
)

# Timeout an effect
timed_effect = (
    from_async(lambda: asyncio.sleep(2))
    .timeout(Duration.seconds(1))  # Fail after 1 second
)
```

## Best Practices

### 1. Use Type Annotations

```python
# Good: Clear about what services are needed and what errors are possible
def fetch_user(id: int) -> Effect[Database | Logger, UserError, User]:
    ...

# Avoid: Too generic, loses type safety
def fetch_user(id: int) -> Effect[Any, Any, Any]:
    ...
```

### 2. Compose Small Effects

```python
# Good: Small, focused effects
def validate_id(id: int) -> Effect[Any, str, int]:
    if id <= 0:
        return fail("Invalid ID")
    return succeed(id)

def fetch_from_db(id: int) -> Effect[Database, str, User]:
    # ... implementation

def get_user(id: int) -> Effect[Database, str, User]:
    return validate_id(id).flat_map(fetch_from_db)

# Avoid: Monolithic effects with mixed concerns
def get_user_big(id: int) -> Effect[Database, str, User]:
    # validation + database + logging + caching all mixed together
    ...
```

### 3. Handle Errors at the Right Level

```python
# Handle specific errors where you can recover
user_effect = (
    fetch_user(123)
    .catch_all(lambda err: 
        fetch_user_from_cache(123) if "database" in str(err).lower() 
        else fail(err)
    )
)

# Let errors bubble up when you can't handle them meaningfully
def low_level_operation() -> Effect[Any, DatabaseError, str]:
    return database_query("SELECT...")  # Don't catch here

def high_level_operation() -> Effect[Any, str, str]:
    return (
        low_level_operation()
        .catch_all(lambda db_err: succeed(f"Database unavailable: {db_err}"))
    )
```

### 4. Use Proper Resource Management

```python
# Good: Always use Scope for resources
async def with_resources():
    scope = Scope()
    env = await ResourceLayer.build_scoped(Context(), scope)
    
    try:
        result = await my_effect._run(env)
        return result
    finally:
        await scope.close()  # Guaranteed cleanup

# Better: Use scoped operations
async def with_resources_scoped():
    return await my_effect._run_scoped_with(ResourceLayer)
```

## What's Next?

- :octicons-arrow-right-24: [Layers & Scope](layers_scope.md) - Resource management
- :octicons-arrow-right-24: [Runtime & Fibers](runtime_fibers.md) - Concurrent execution  
- :octicons-arrow-right-24: [Concurrency Guide](../guides/concurrency.md) - Practical patterns
- :octicons-arrow-right-24: [Core API Reference](../reference/core.md) - Complete API

