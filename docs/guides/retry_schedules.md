# Retry & Schedules Guide

Robust applications need to handle failures gracefully. effectpy provides powerful retry and repeat mechanisms through the `Schedule` abstraction, allowing you to implement sophisticated backoff strategies and failure recovery patterns.

## Understanding Schedules

A `Schedule` defines when and how to retry or repeat operations. Schedules are composable, testable, and provide fine-grained control over timing and conditions.

### Basic Retry Patterns

```python
import asyncio
from effectpy import *

def unreliable_service() -> Effect[Any, str, str]:
    import random
    if random.random() < 0.7:  # 70% failure rate
        return fail("Service temporarily unavailable")
    return succeed("Service response")

async def basic_retry_example():
    # Simple retry: try up to 3 times
    reliable_service = unreliable_service().retry(Schedule.recurs(3))
    
    try:
        result = await reliable_service._run(Context())
        print(f"✅ Success: {result}")
    except Failure as f:
        print(f"❌ Failed after retries: {f.error}")

asyncio.run(basic_retry_example())
```

### Exponential Backoff

```python
import asyncio
from effectpy import *

async def exponential_backoff_example():
    def flaky_network_call() -> Effect[Any, str, dict]:
        import random
        if random.random() < 0.8:  # 80% failure rate
            return fail("Network timeout")
        return succeed({"status": "ok", "data": "Network response"})
    
    # Exponential backoff: 0.1s, 0.2s, 0.4s, 0.8s...
    schedule = Schedule.exponential(initial=0.1).jittered()
    
    robust_call = flaky_network_call().retry(schedule.and_then(Schedule.recurs(5)))
    
    start_time = time.time()
    try:
        result = await robust_call._run(Context())
        elapsed = time.time() - start_time
        print(f"✅ Success after {elapsed:.2f}s: {result}")
    except Failure as f:
        elapsed = time.time() - start_time
        print(f"❌ Failed after {elapsed:.2f}s: {f.error}")

asyncio.run(exponential_backoff_example())
```

## Common Schedule Types

### Fixed Intervals

```python
import asyncio
from effectpy import *

async def fixed_schedule_examples():
    # Retry every 1 second, up to 3 times
    every_second = Schedule.spaced(1.0).and_then(Schedule.recurs(3))
    
    # Retry immediately, up to 5 times
    immediate_retry = Schedule.recurs(5)
    
    # Single retry after 2 seconds
    delayed_single = Schedule.spaced(2.0)
    
    def test_service() -> Effect[Any, str, str]:
        import random
        if random.random() < 0.6:
            return fail("Random failure")
        return succeed("Success!")
    
    # Test different schedules
    schedules = [
        ("Immediate retry", immediate_retry),
        ("Every second", every_second),
        ("Delayed single", delayed_single)
    ]
    
    for name, schedule in schedules:
        print(f"\n🧪 Testing: {name}")
        start = time.time()
        
        try:
            result = await test_service().retry(schedule)._run(Context())
            elapsed = time.time() - start
            print(f"✅ {name}: Success after {elapsed:.2f}s")
        except Failure as f:
            elapsed = time.time() - start
            print(f"❌ {name}: Failed after {elapsed:.2f}s")

asyncio.run(fixed_schedule_examples())
```

### Conditional Retry

```python
import asyncio
from effectpy import *

class NetworkError(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"HTTP {code}: {message}")

async def conditional_retry_example():
    def api_call() -> Effect[Any, NetworkError, dict]:
        import random
        
        # Simulate different error types
        rand = random.random()
        if rand < 0.3:
            return fail(NetworkError(500, "Internal Server Error"))  # Retriable
        elif rand < 0.5:
            return fail(NetworkError(404, "Not Found"))  # Don't retry
        elif rand < 0.7:
            return fail(NetworkError(429, "Too Many Requests"))  # Retry with backoff
        else:
            return succeed({"status": "success", "data": "API response"})
    
    # Custom retry logic based on error type
    def should_retry(error: NetworkError) -> bool:
        # Retry on server errors and rate limiting
        return error.code in [500, 502, 503, 429]
    
    def get_schedule(error: NetworkError) -> Schedule:
        if error.code == 429:  # Rate limited
            return Schedule.exponential(2.0).and_then(Schedule.recurs(3))  # Longer backoff
        else:  # Server errors
            return Schedule.exponential(0.5).and_then(Schedule.recurs(5))  # Shorter backoff
    
    # Implement conditional retry
    def smart_retry(effect: Effect[Any, NetworkError, dict]) -> Effect[Any, NetworkError, dict]:
        return effect.catch_all(lambda error:
            effect.retry(get_schedule(error)) if should_retry(error) else fail(error)
        )
    
    try:
        result = await smart_retry(api_call())._run(Context())
        print(f"✅ API call succeeded: {result}")
    except Failure as f:
        error = f.error
        print(f"❌ API call failed: {error}")

asyncio.run(conditional_retry_example())
```

## Repeat Operations

While retry is for handling failures, repeat is for recurring operations:

### Periodic Tasks

```python
import asyncio
from effectpy import *

async def repeat_example():
    def health_check() -> Effect[Any, str, dict]:
        import time
        return succeed({
            "timestamp": time.time(),
            "status": "healthy",
            "uptime": "5h 23m"
        })
    
    def send_heartbeat() -> Effect[Any, str, None]:
        async def impl(ctx: Context):
            result = await health_check()._run(ctx)
            print(f"💓 Heartbeat: {result}")
            return None
        return Effect(impl)
    
    # Send heartbeat every 2 seconds, up to 5 times
    heartbeat_schedule = Schedule.spaced(2.0).and_then(Schedule.recurs(5))
    
    print("🚀 Starting heartbeat monitoring...")
    try:
        await send_heartbeat().repeat(heartbeat_schedule)._run(Context())
        print("✅ Heartbeat monitoring completed")
    except Exception as e:
        print(f"❌ Heartbeat monitoring failed: {e}")

asyncio.run(repeat_example())
```

### Data Processing Pipeline

```python
import asyncio
from effectpy import *

async def pipeline_repeat_example():
    class DataProcessor:
        def __init__(self):
            self.batch_count = 0
        
        def process_batch(self) -> Effect[Any, str, dict]:
            async def impl(ctx: Context):
                self.batch_count += 1
                
                # Simulate processing
                await asyncio.sleep(0.5)
                
                # Simulate occasional failures
                if self.batch_count == 3:  # Fail on 3rd batch
                    raise ValueError("Processing error in batch 3")
                
                return {
                    "batch": self.batch_count,
                    "processed_items": self.batch_count * 100,
                    "status": "complete"
                }
            
            return Effect(impl)
    
    processor = DataProcessor()
    
    # Process batches with retry on failure
    def robust_batch_processing() -> Effect[Any, str, dict]:
        return (processor.process_batch()
                .retry(Schedule.exponential(0.1).and_then(Schedule.recurs(2)))
                .map(lambda result: {
                    **result,
                    "retry_resilient": True
                }))
    
    # Process batches every 1 second, up to 6 batches
    processing_schedule = Schedule.spaced(1.0).and_then(Schedule.recurs(6))
    
    print("🔄 Starting batch processing pipeline...")
    
    try:
        await robust_batch_processing().repeat(processing_schedule)._run(Context())
        print("✅ Pipeline completed successfully")
    except Failure as f:
        print(f"❌ Pipeline failed: {f.error}")

asyncio.run(pipeline_repeat_example())
```

## Advanced Schedule Composition

### Combining Schedules

```python
import asyncio
from effectpy import *

async def schedule_composition_example():
    def unstable_service() -> Effect[Any, str, str]:
        import random
        if random.random() < 0.85:  # 85% failure rate
            return fail("Service overloaded")
        return succeed("Service available")
    
    # Complex schedule: try 3 times immediately, then exponential backoff
    immediate_retries = Schedule.recurs(3)
    exponential_backoff = Schedule.exponential(1.0).and_then(Schedule.recurs(5))
    
    # Combine: immediate retries, then if still failing, exponential backoff
    combined_schedule = immediate_retries.and_then(exponential_backoff)
    
    print("🔧 Testing combined retry strategy...")
    start_time = time.time()
    
    try:
        result = await unstable_service().retry(combined_schedule)._run(Context())
        elapsed = time.time() - start_time
        print(f"✅ Success after {elapsed:.2f}s: {result}")
    except Failure as f:
        elapsed = time.time() - start_time
        print(f"❌ Failed after {elapsed:.2f}s: {f.error}")

asyncio.run(schedule_composition_example())
```

### Schedule with Timeout

```python
import asyncio
from effectpy import *

async def schedule_with_timeout_example():
    def slow_service() -> Effect[Any, str, str]:
        async def impl(ctx: Context):
            # Simulate slow response
            await asyncio.sleep(2.0)
            return "Slow service response"
        return Effect(impl)
    
    # Retry with timeout: each attempt has 1s timeout, retry 3 times
    def timed_retry_service() -> Effect[Any, str, str]:
        return (slow_service()
                .timeout(Duration.seconds(1))  # 1 second timeout per attempt
                .catch_all(lambda _: fail("Request timed out"))
                .retry(Schedule.spaced(0.5).and_then(Schedule.recurs(3))))
    
    print("⏰ Testing service with timeout and retry...")
    start_time = time.time()
    
    try:
        result = await timed_retry_service()._run(Context())
        elapsed = time.time() - start_time
        print(f"✅ Success after {elapsed:.2f}s: {result}")
    except Failure as f:
        elapsed = time.time() - start_time
        print(f"❌ Failed after {elapsed:.2f}s: {f.error}")

asyncio.run(schedule_with_timeout_example())
```

## Testing Schedules

### Deterministic Testing

```python
import asyncio
from effectpy import *

async def test_schedule_behavior():
    """Test schedule behavior with controlled timing"""
    
    test_clock = TestClock()
    scope = Scope()
    env = await TestClockLayer(test_clock).build_scoped(Context(), scope)
    
    attempt_count = 0
    
    def counting_service() -> Effect[Clock, str, str]:
        async def impl(ctx: Context):
            nonlocal attempt_count
            attempt_count += 1
            
            clock = ctx.get(Clock)
            current_time = await clock.current_time()
            
            if attempt_count < 3:  # Fail first 2 attempts
                return fail(f"Attempt {attempt_count} failed at time {current_time}")
            
            return succeed(f"Success on attempt {attempt_count} at time {current_time}")
        
        return Effect(impl)
    
    # Test exponential backoff schedule
    schedule = Schedule.exponential(1.0).and_then(Schedule.recurs(5))
    
    # Start the retry operation
    retry_fiber = asyncio.create_task(
        counting_service().retry(schedule)._run(env)
    )
    
    # Control time advancement
    await asyncio.sleep(0.01)  # Let first attempt start
    
    # First retry after 1s
    test_clock.advance(1.0)
    await asyncio.sleep(0.01)
    
    # Second retry after 2s more (exponential backoff)
    test_clock.advance(2.0)
    await asyncio.sleep(0.01)
    
    # Service should succeed on 3rd attempt
    result = await retry_fiber
    print(f"🧪 Test result: {result}")
    print(f"📊 Total attempts: {attempt_count}")
    
    await scope.close()

asyncio.run(test_schedule_behavior())
```

## Best Practices

### 1. Choose Appropriate Schedules

```python
# ✅ Good: Match schedule to failure type
network_retry = Schedule.exponential(0.5).jittered().and_then(Schedule.recurs(3))  # Network issues
database_retry = Schedule.spaced(1.0).and_then(Schedule.recurs(5))  # Database locks
immediate_retry = Schedule.recurs(2)  # Transient failures

# ❌ Avoid: One-size-fits-all approach
generic_retry = Schedule.recurs(10)  # Too simplistic
```

### 2. Add Jitter to Prevent Thundering Herd

```python
# ✅ Good: Jittered exponential backoff
jittered_schedule = Schedule.exponential(1.0).jittered().and_then(Schedule.recurs(3))

# ❌ Avoid: Fixed timing that can cause thundering herd
fixed_schedule = Schedule.exponential(1.0).and_then(Schedule.recurs(3))
```

### 3. Set Reasonable Limits

```python
# ✅ Good: Bounded retry attempts and timing
bounded_retry = (Schedule.exponential(0.1)
                 .jittered()
                 .and_then(Schedule.recurs(5))  # Max 5 retries
                 .up_to(Duration.seconds(30)))  # Max 30s total

# ❌ Avoid: Unbounded retries
unbounded_retry = Schedule.exponential(1.0)  # Could retry forever
```

### 4. Log Retry Attempts

```python
# ✅ Good: Observable retry behavior
def logged_retry(effect: Effect[Any, E, A], schedule: Schedule) -> Effect[Logger, E, A]:
    return effect.retry(schedule).tap_error(
        lambda error: service(Logger).flat_map(
            lambda logger: sync(lambda: logger.warning(f"Retry attempt failed: {error}"))
        )
    )
```

## What's Next?

- **→ [Effects](../concepts/effects.md)** - Understanding error handling in Effects
- **→ [Concurrency Guide](concurrency.md)** - Retry patterns in concurrent operations
- **→ [Observability](../concepts/observability.md)** - Monitoring retry behavior
- **→ [Core API Reference](../reference/core.md)** - Complete Schedule API

