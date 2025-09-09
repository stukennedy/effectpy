# Concurrency Guide

Structured concurrency is one of effectpy's greatest strengths. Unlike raw `asyncio`, effectpy provides safe, composable primitives that prevent common concurrency bugs like resource leaks, zombie tasks, and race conditions.

This guide covers practical patterns for concurrent programming with effectpy.

## The Problem with Raw asyncio

Traditional `asyncio` concurrency is error-prone:

```python
import asyncio

async def risky_asyncio():
    # ❌ Easy to create zombie tasks
    task1 = asyncio.create_task(fetch_data("service1"))
    task2 = asyncio.create_task(fetch_data("service2"))
    
    try:
        result1 = await task1
        result2 = await task2
        return result1, result2
    except Exception:
        # ❌ Tasks may still be running!
        # Need manual cleanup
        task1.cancel()
        task2.cancel()
        raise
```

Problems:
- **Manual task management** - easy to forget cleanup
- **Exception safety** - tasks may leak on errors
- **Cancellation complexity** - hard to get right
- **No structured composition** - difficult to combine patterns

## The effectpy Solution

effectpy provides structured concurrency with automatic cleanup:

```python
import asyncio
from effectpy import *

async def safe_effectpy():
    # ✅ Automatic cleanup, structured composition
    result1, result2 = await zip_par(
        fetch_data("service1"),
        fetch_data("service2")
    )._run(Context())
    return result1, result2
```

Benefits:
- **Automatic cleanup** - no leaked tasks
- **Exception safety** - all operations cancelled on error
- **Composable** - combine with other patterns easily
- **Type safe** - proper error propagation

## Core Concurrency Primitives

### zip_par: Parallel Execution

Run multiple effects concurrently and wait for all to complete:

```python
import asyncio
from effectpy import *

async def fetch_data(name: str, delay: float) -> Effect[Any, str, dict]:
    await asyncio.sleep(delay)
    if delay > 0.5:  # Simulate failure for slow requests
        return fail(f"{name} timeout")
    return succeed({"service": name, "data": f"Data from {name}"})

async def parallel_fetching():
    # All three run concurrently, wait for all
    try:
        results = await zip_par(
            fetch_data("Auth", 0.1),
            fetch_data("User", 0.2),
            fetch_data("Profile", 0.15)
        )._run(Context())
        
        auth, user, profile = results
        print(f"All succeeded: {auth}, {user}, {profile}")
        
    except Failure as f:
        print(f"At least one failed: {f.error}")
        # All other operations automatically cancelled

asyncio.run(parallel_fetching())
```

### race: First to Complete

Run multiple effects concurrently, return the first successful result:

```python
async def race_example():
    # Try multiple data sources, use whichever responds first
    winner = await race(
        fetch_data("Primary", 0.3),
        fetch_data("Backup", 0.2),  
        fetch_data("Fallback", 0.4)
    )._run(Context())
    
    print(f"Winner: {winner}")
    # Other operations automatically cancelled

asyncio.run(race_example())
```

### for_each_par: Parallel Mapping

Apply an effect to each item in a collection, with controlled parallelism:

```python
async def parallel_processing():
    user_ids = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    
    # Process users with maximum 3 concurrent operations
    results = await for_each_par(
        items=user_ids,
        effect_fn=lambda user_id: fetch_data(f"User{user_id}", 0.1),
        parallelism=3
    )._run(Context())
    
    print(f"Processed {len(results)} users")
    return results

asyncio.run(parallel_processing())
```

## Advanced Patterns

### Timeout and Fallback

Combine racing with timeouts and fallback strategies:

```python
from effectpy import *

def with_timeout_and_fallback(
    primary: Effect[Any, str, str],
    timeout_ms: int,
    fallback: Effect[Any, str, str]
) -> Effect[Any, str, str]:
    
    # Race primary operation against timeout
    timed_primary = race(
        primary,
        sleep(timeout_ms / 1000).flat_map(lambda _: fail("timeout"))
    )
    
    # If timed primary fails, try fallback
    return timed_primary.catch_all(lambda _: fallback)

async def timeout_example():
    slow_service = fetch_data("SlowService", 2.0)  # 2 second delay
    fast_fallback = succeed({"service": "Cache", "data": "Cached data"})
    
    result = await with_timeout_and_fallback(
        primary=slow_service,
        timeout_ms=500,  # 500ms timeout
        fallback=fast_fallback
    )._run(Context())
    
    print(f"Result: {result}")

asyncio.run(timeout_example())
```

### Circuit Breaker Pattern

Implement circuit breaker using effectpy's error handling:

```python
import time
from dataclasses import dataclass
from effectpy import *

@dataclass
class CircuitBreakerState:
    failures: int = 0
    last_failure: float = 0
    is_open: bool = False

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, timeout_seconds: float = 60):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.state = CircuitBreakerState()
    
    def call(self, effect: Effect[Any, str, str]) -> Effect[Any, str, str]:
        def wrapped_effect(ctx: Context) -> Effect[Any, str, str]:
            now = time.time()
            
            # Check if circuit is open and timeout has passed
            if self.state.is_open:
                if now - self.state.last_failure > self.timeout_seconds:
                    self.state.is_open = False
                    self.state.failures = 0
                else:
                    return fail("Circuit breaker is OPEN")
            
            # Try the effect
            return (
                effect
                .map(lambda result: self._on_success(result))
                .catch_all(lambda error: self._on_failure(error, now))
            )
        
        return Effect(lambda ctx: wrapped_effect(ctx)._run(ctx))
    
    def _on_success(self, result: str) -> str:
        self.state.failures = 0
        self.state.is_open = False
        return result
    
    def _on_failure(self, error: str, now: float) -> Effect[Any, str, str]:
        self.state.failures += 1
        self.state.last_failure = now
        
        if self.state.failures >= self.failure_threshold:
            self.state.is_open = True
            return fail(f"Circuit breaker OPENED due to: {error}")
        
        return fail(error)

async def circuit_breaker_example():
    cb = CircuitBreaker(failure_threshold=2, timeout_seconds=5)
    
    # Unreliable service that fails most of the time
    def unreliable_service() -> Effect[Any, str, str]:
        import random
        if random.random() < 0.8:  # 80% failure rate
            return fail("Service unavailable")
        return succeed("Service response")
    
    # Try the service multiple times
    for i in range(10):
        try:
            result = await cb.call(unreliable_service())._run(Context())
            print(f"Call {i+1}: SUCCESS - {result}")
        except Failure as f:
            print(f"Call {i+1}: FAILED - {f.error}")
        
        await asyncio.sleep(0.5)

asyncio.run(circuit_breaker_example())
```

### Fan-out/Fan-in Pattern

Distribute work across multiple workers, then collect results:

```python
async def fan_out_fan_in_example():
    # Large dataset to process
    data = list(range(100))
    
    # Split into chunks for parallel processing
    chunk_size = 20
    chunks = [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]
    
    # Process each chunk in parallel
    def process_chunk(chunk: list) -> Effect[Any, str, int]:
        async def impl(ctx: Context):
            # Simulate processing
            await asyncio.sleep(0.1)
            return sum(chunk)  # Sum the chunk
        return Effect(impl)
    
    # Fan-out: distribute work
    chunk_effects = [process_chunk(chunk) for chunk in chunks]
    
    # Fan-in: collect all results
    chunk_results = await zip_par(*chunk_effects)._run(Context())
    
    # Final aggregation
    total = sum(chunk_results)
    print(f"Processed {len(data)} items, total: {total}")
    return total

asyncio.run(fan_out_fan_in_example())
```

## Error Handling in Concurrent Code

### Fail-Fast vs. Fail-Safe

```python
# Fail-fast: Stop on first error (zip_par)
async def fail_fast():
    try:
        results = await zip_par(
            succeed("ok1"),
            fail("error!"),
            succeed("ok3")
        )._run(Context())
    except Failure as f:
        print(f"Failed fast: {f.error}")
        # Third operation was cancelled

# Fail-safe: Collect all results, including errors
async def fail_safe():
    effects = [
        succeed("ok1"),
        fail("error!"),
        succeed("ok3")
    ]
    
    # Run all, convert failures to Options
    safe_effects = [
        effect.map(lambda x: Some(x)).catch_all(lambda _: succeed(NONE))
        for effect in effects
    ]
    
    results = await zip_par(*safe_effects)._run(Context())
    successes = [r.value for r in results if r.is_some()]
    failures = len([r for r in results if r.is_none()])
    
    print(f"Successes: {successes}, Failures: {failures}")

asyncio.run(fail_fast())
asyncio.run(fail_safe())
```

### Partial Failure Handling

```python
from effectpy import *

async def partial_failure_example():
    # Critical services (must succeed)
    critical_effects = [
        fetch_data("Auth", 0.1),
        fetch_data("Core", 0.1)
    ]
    
    # Optional services (can fail)
    optional_effects = [
        fetch_data("Analytics", 0.3).catch_all(lambda _: succeed({"service": "Analytics", "data": "unavailable"})),
        fetch_data("Recommendations", 0.4).catch_all(lambda _: succeed({"service": "Recommendations", "data": "unavailable"}))
    ]
    
    # Critical services must all succeed
    critical_results = await zip_par(*critical_effects)._run(Context())
    
    # Optional services run in parallel but failures are handled
    optional_results = await zip_par(*optional_effects)._run(Context())
    
    print(f"Critical: {critical_results}")
    print(f"Optional: {optional_results}")

asyncio.run(partial_failure_example())
```

## Testing Concurrent Code

### Testing with TestClock

effectpy's `TestClock` makes concurrent code deterministic for testing:

```python
import asyncio
from effectpy import *

async def time_dependent_operation() -> Effect[Clock, str, str]:
    async def impl(ctx: Context):
        clock = ctx.get(Clock)
        start = await clock.current_time()
        
        await clock.sleep(1.0)  # Wait 1 second
        
        end = await clock.current_time()
        return f"Operation took {end - start:.1f}s"
    
    return Effect(impl)

async def test_with_real_clock():
    scope = Scope()
    env = await ClockLayer.build_scoped(Context(), scope)
    
    start_time = time.time()
    result = await time_dependent_operation()._run(env)
    actual_time = time.time() - start_time
    
    print(f"Real clock: {result}, actual time: {actual_time:.1f}s")
    await scope.close()

async def test_with_test_clock():
    test_clock = TestClock()
    scope = Scope()
    env = await TestClockLayer(test_clock).build_scoped(Context(), scope)
    
    # Run operation in background
    operation_fiber = asyncio.create_task(time_dependent_operation()._run(env))
    
    # Advance test clock
    await asyncio.sleep(0.01)  # Let operation start
    test_clock.advance(1.0)  # Advance by 1 second instantly
    
    result = await operation_fiber
    print(f"Test clock: {result} (instant)")
    await scope.close()

asyncio.run(test_with_real_clock())
asyncio.run(test_with_test_clock())
```

### Testing Race Conditions

```python
async def test_race_conditions():
    test_clock = TestClock()
    scope = Scope()
    env = await TestClockLayer(test_clock).build_scoped(Context(), scope)
    
    def timed_effect(name: str, delay: float) -> Effect[Clock, str, str]:
        async def impl(ctx: Context):
            clock = ctx.get(Clock)
            await clock.sleep(delay)
            return f"{name} completed"
        return Effect(impl)
    
    # Start race
    race_fiber = asyncio.create_task(
        race(
            timed_effect("Fast", 1.0),
            timed_effect("Slow", 2.0)
        )._run(env)
    )
    
    # Control exactly when each effect completes
    await asyncio.sleep(0.01)
    test_clock.advance(1.0)  # Fast effect completes
    
    result = await race_fiber
    assert result == "Fast completed"
    print(f"Race result: {result}")
    
    await scope.close()

asyncio.run(test_race_conditions())
```

## Performance Patterns

### Batching Operations

```python
async def batch_processing_example():
    # Large number of items to process
    items = list(range(1000))
    
    def process_batch(batch: list) -> Effect[Any, str, list]:
        async def impl(ctx: Context):
            # Simulate batch processing (more efficient than individual items)
            await asyncio.sleep(0.1)
            return [item * 2 for item in batch]
        return Effect(impl)
    
    # Create batches
    batch_size = 50
    batches = [items[i:i+batch_size] for i in range(0, len(items), batch_size)]
    
    # Process batches with limited parallelism
    batch_results = await for_each_par(
        items=batches,
        effect_fn=process_batch,
        parallelism=5  # Max 5 concurrent batches
    )._run(Context())
    
    # Flatten results
    results = [item for batch in batch_results for item in batch]
    print(f"Processed {len(results)} items in {len(batches)} batches")
    return results

asyncio.run(batch_processing_example())
```

### Connection Pool Pattern

```python
from effectpy import *

class Connection:
    def __init__(self, id: int):
        self.id = id
        self.in_use = False
    
    async def query(self, sql: str) -> str:
        await asyncio.sleep(0.1)
        return f"Connection {self.id}: {sql} -> result"

class ConnectionPool:
    def __init__(self, size: int):
        self.connections = [Connection(i) for i in range(size)]
        self.available = Queue(maxsize=size)
        
        # Initialize pool
        for conn in self.connections:
            self.available.put_nowait(conn)
    
    async def acquire(self) -> Connection:
        return await self.available.get()
    
    async def release(self, conn: Connection):
        conn.in_use = False
        await self.available.put(conn)

def with_connection(pool: ConnectionPool) -> Effect[Any, str, Connection]:
    return acquire_release(
        acquire=from_async(pool.acquire),
        release=lambda conn: from_async(lambda: pool.release(conn))
    )

async def connection_pool_example():
    pool = ConnectionPool(size=3)
    
    def db_operation(query: str) -> Effect[Any, str, str]:
        return (
            with_connection(pool)
            .flat_map(lambda conn: from_async(lambda: conn.query(query)))
        )
    
    # Many concurrent operations with limited pool
    operations = [
        db_operation(f"SELECT {i}") for i in range(10)
    ]
    
    # Limited by pool size (3), but will complete all operations
    results = await for_each_par(
        items=operations,
        effect_fn=lambda op: op,
        parallelism=10  # Try 10, but pool limits to 3
    )._run(Context())
    
    print(f"Completed {len(results)} database operations")
    return results

asyncio.run(connection_pool_example())
```

## Best Practices

### 1. Always Use Structured Concurrency

```python
# ✅ Good: Structured with automatic cleanup
async def good_concurrency():
    result = await zip_par(
        fetch_data("service1"),
        fetch_data("service2")
    )._run(Context())
    return result

# ❌ Avoid: Raw asyncio tasks
async def avoid_raw_tasks():
    task1 = asyncio.create_task(fetch_data("service1"))
    task2 = asyncio.create_task(fetch_data("service2"))
    # Manual cleanup required, error-prone
    return await task1, await task2
```

### 2. Control Parallelism

```python
# ✅ Good: Limit concurrent operations
results = await for_each_par(
    items=large_dataset,
    effect_fn=process_item,
    parallelism=10  # Reasonable limit
)._run(Context())

# ❌ Avoid: Unbounded parallelism
effects = [process_item(item) for item in large_dataset]  # Could be thousands!
results = await zip_par(*effects)._run(Context())
```

### 3. Handle Failures Appropriately

```python
# ✅ Good: Choose the right failure semantics
# Fail-fast for critical operations
critical = await zip_par(auth_check, load_config)._run(Context())

# Fail-safe for optional operations  
optional_results = await zip_par(
    *[op.catch_all(lambda _: succeed(None)) for op in optional_ops]
)._run(Context())
```

### 4. Use TestClock for Testing

```python
# ✅ Good: Deterministic time-based testing
async def test_timeout_behavior():
    test_clock = TestClock()
    scope = Scope()
    env = await TestClockLayer(test_clock).build_scoped(Context(), scope)
    
    # Test exact timing without waiting
    operation = time_dependent_effect.timeout(Duration.seconds(5))
    
    fiber = asyncio.create_task(operation._run(env))
    test_clock.advance(6.0)  # Past timeout
    
    with pytest.raises(Failure):
        await fiber
    
    await scope.close()
```

## What's Next?

- :octicons-arrow-right-24: [Runtime & Fibers](../concepts/runtime_fibers.md) - Deeper dive into concurrent execution
- :octicons-arrow-right-24: [Streams & Channels](../concepts/streams_channels.md) - Streaming concurrency patterns
- :octicons-arrow-right-24: [Retry & Schedules](retry_schedules.md) - Robust error recovery
- :octicons-arrow-right-24: [Core API Reference](../reference/core.md) - Complete concurrency API

