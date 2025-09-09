# Runtime & Fibers

The Runtime system is effectpy's foundation for concurrent execution. While you can run effects directly with `._run(context)`, the Runtime provides advanced features like fiber management, supervision, and structured concurrency.

**Key concepts:**
- **Runtime**: Manages effect execution and fiber lifecycle
- **Fiber**: A lightweight async task with structured cancellation
- **Supervision**: Automatic restart and error handling for long-running processes

## Understanding Fibers

A Fiber is effectpy's unit of concurrent execution - similar to an asyncio Task but with structured semantics and better error handling.

### Basic Fiber Operations

```python
import asyncio
from effectpy import *

async def fiber_basics():
    runtime = Runtime()
    
    def long_running_task() -> Effect[Any, str, str]:
        async def impl(ctx: Context):
            for i in range(5):
                await asyncio.sleep(0.5)
                print(f"Working... {i+1}/5")
            return "Task completed!"
        return Effect(impl)
    
    # Fork a fiber (starts immediately)
    fiber = runtime.fork(long_running_task())
    print(f"Fiber started: {fiber}")
    
    # Do other work while fiber runs
    await asyncio.sleep(1.0)
    print("Doing other work...")
    
    # Wait for fiber completion
    result = await fiber.await_()
    print(f"Result: {result}")
    
    # Clean up
    await runtime.shutdown()

asyncio.run(fiber_basics())
```

### Fiber Lifecycle

```python
import asyncio
from effectpy import *

async def fiber_lifecycle():
    runtime = Runtime()
    
    def monitored_task(task_id: int) -> Effect[Any, str, str]:
        async def impl(ctx: Context):
            try:
                for i in range(10):
                    await asyncio.sleep(0.2)
                    print(f"Task {task_id}: step {i+1}/10")
                return f"Task {task_id} completed"
            except asyncio.CancelledError:
                print(f"Task {task_id} was cancelled")
                raise
        return Effect(impl)
    
    # Start multiple fibers
    fibers = []
    for i in range(3):
        fiber = runtime.fork(monitored_task(i))
        fibers.append(fiber)
        print(f"Started fiber {i}: {fiber}")
    
    # Let them run briefly
    await asyncio.sleep(1.0)
    
    # Interrupt one fiber
    print("Interrupting fiber 1...")
    await fibers[1].interrupt()
    
    # Wait for others to complete
    for i, fiber in enumerate(fibers):
        if i == 1:  # Skip interrupted fiber
            continue
        try:
            result = await fiber.await_()
            print(f"Fiber {i} result: {result}")
        except Exception as e:
            print(f"Fiber {i} failed: {e}")
    
    await runtime.shutdown()

asyncio.run(fiber_lifecycle())
```

## Runtime Features

### Fiber Management

```python
import asyncio
from effectpy import *

async def fiber_management():
    runtime = Runtime()
    
    def worker_task(worker_id: int, work_time: float) -> Effect[Any, str, str]:
        async def impl(ctx: Context):
            print(f"Worker {worker_id} starting")
            await asyncio.sleep(work_time)
            print(f"Worker {worker_id} finished")
            return f"Worker {worker_id} result"
        return Effect(impl)
    
    # Fork multiple workers
    workers = []
    for i in range(5):
        fiber = runtime.fork(worker_task(i, 0.5 + i * 0.2))
        workers.append((i, fiber))
    
    print(f"Started {len(workers)} workers")
    
    # Monitor and collect results
    results = {}
    for worker_id, fiber in workers:
        try:
            result = await fiber.await_()
            results[worker_id] = result
            print(f"✅ Worker {worker_id}: {result}")
        except Exception as e:
            results[worker_id] = f"ERROR: {e}"
            print(f"❌ Worker {worker_id}: {e}")
    
    print(f"Collected {len(results)} results")
    await runtime.shutdown()

asyncio.run(fiber_management())
```

### Error Handling and Supervision

```python
import asyncio
from effectpy import *

class TaskSupervisor:
    def __init__(self, runtime: Runtime):
        self.runtime = runtime
        self.restart_count = 0
        self.max_restarts = 3
    
    def supervise_task(self, task_effect: Effect[Any, str, str], task_name: str):
        """Supervise a task with automatic restart on failure"""
        
        async def supervised():
            while self.restart_count < self.max_restarts:
                try:
                    print(f"🚀 Starting {task_name} (attempt {self.restart_count + 1})")
                    fiber = self.runtime.fork(task_effect)
                    result = await fiber.await_()
                    print(f"✅ {task_name} completed: {result}")
                    return result
                
                except Exception as e:
                    self.restart_count += 1
                    print(f"❌ {task_name} failed: {e}")
                    
                    if self.restart_count < self.max_restarts:
                        wait_time = 2 ** self.restart_count  # Exponential backoff
                        print(f"⏳ Restarting {task_name} in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    else:
                        print(f"💥 {task_name} exceeded max restarts")
                        raise
            
        return Effect(lambda ctx: supervised())

async def supervision_example():
    runtime = Runtime()
    supervisor = TaskSupervisor(runtime)
    
    def unreliable_task() -> Effect[Any, str, str]:
        async def impl(ctx: Context):
            import random
            await asyncio.sleep(0.5)
            
            if random.random() < 0.7:  # 70% failure rate
                raise ValueError("Random task failure!")
            
            return "Task succeeded!"
        
        return Effect(impl)
    
    # Supervise the unreliable task
    try:
        supervised = supervisor.supervise_task(unreliable_task(), "UnreliableWorker")
        result = await supervised._run(Context())
        print(f"Final result: {result}")
    except Exception as e:
        print(f"Task permanently failed: {e}")
    
    await runtime.shutdown()

asyncio.run(supervision_example())
```

### Structured Concurrency with Runtime

```python
import asyncio
from effectpy import *

async def structured_concurrency():
    runtime = Runtime()
    
    def data_processor(data_id: int, processing_time: float) -> Effect[Any, str, dict]:
        async def impl(ctx: Context):
            print(f"📊 Processing data {data_id}")
            await asyncio.sleep(processing_time)
            
            # Simulate occasional failures
            if data_id == 3:  # This one always fails
                raise ValueError(f"Processing failed for data {data_id}")
            
            return {"data_id": data_id, "result": f"processed_{data_id}"}
        
        return Effect(impl)
    
    # Process multiple data items concurrently
    data_items = [(i, 0.5 + i * 0.1) for i in range(1, 6)]
    
    # Fork all processors
    processors = []
    for data_id, proc_time in data_items:
        effect = data_processor(data_id, proc_time)
        fiber = runtime.fork(effect)
        processors.append((data_id, fiber))
    
    print(f"🚀 Started {len(processors)} processors")
    
    # Collect results, handling failures gracefully
    successful_results = []
    failed_items = []
    
    for data_id, fiber in processors:
        try:
            result = await fiber.await_()
            successful_results.append(result)
            print(f"✅ Data {data_id}: Success")
        except Exception as e:
            failed_items.append((data_id, str(e)))
            print(f"❌ Data {data_id}: Failed - {e}")
    
    print(f"\n📈 Processing Summary:")
    print(f"  Successful: {len(successful_results)}")
    print(f"  Failed: {len(failed_items)}")
    
    if failed_items:
        print("  Failed items:")
        for data_id, error in failed_items:
            print(f"    - Data {data_id}: {error}")
    
    await runtime.shutdown()

asyncio.run(structured_concurrency())
```

## Runtime vs Direct Execution

### When to Use Runtime

```python
import asyncio
from effectpy import *

# ✅ Good: Use runtime for long-running processes
async def long_running_service():
    runtime = Runtime()
    
    def background_monitor() -> Effect[Any, str, None]:
        async def impl(ctx: Context):
            counter = 0
            while True:  # Infinite loop
                await asyncio.sleep(2.0)
                counter += 1
                print(f"🔍 Monitor check #{counter}")
                
                # Exit condition for demo
                if counter >= 5:
                    break
        
        return Effect(impl)
    
    # Fork background process
    monitor_fiber = runtime.fork(background_monitor())
    
    # Do main application work
    print("🚀 Main application starting...")
    await asyncio.sleep(3.0)
    print("⚙️  Main application working...")
    await asyncio.sleep(4.0)
    print("✅ Main application completed")
    
    # Clean shutdown
    await monitor_fiber.interrupt()
    await runtime.shutdown()

# ✅ Good: Use direct execution for simple tasks  
async def simple_computation():
    def calculate() -> Effect[Any, str, int]:
        return succeed(42 * 2)
    
    result = await calculate()._run(Context())
    print(f"Simple calculation: {result}")

asyncio.run(long_running_service())
asyncio.run(simple_computation())
```

## AnyIO Runtime (Optional)

effectpy supports AnyIO for Trio compatibility:

```python
import asyncio
from effectpy import *

async def anyio_example():
    # Only available if anyio is installed
    try:
        if AnyIORuntime is not None:
            runtime = AnyIORuntime()
            
            def trio_compatible_task() -> Effect[Any, str, str]:
                async def impl(ctx: Context):
                    await asyncio.sleep(0.1)  # Works with both asyncio and trio
                    return "Task completed with AnyIO!"
                
                return Effect(impl)
            
            fiber = runtime.fork(trio_compatible_task())
            result = await fiber.await_()
            print(f"AnyIO result: {result}")
            
            await runtime.shutdown()
        else:
            print("AnyIO runtime not available (install anyio)")
            
    except Exception as e:
        print(f"AnyIO example failed: {e}")

asyncio.run(anyio_example())
```

## Testing with Runtime

```python
import asyncio
from effectpy import *

async def runtime_testing():
    """Test fiber behavior with controlled timing"""
    
    test_clock = TestClock()
    runtime = Runtime()
    
    def timed_task(duration: float, name: str) -> Effect[Clock, str, str]:
        async def impl(ctx: Context):
            clock = ctx.get(Clock)
            start = await clock.current_time()
            
            await clock.sleep(duration)
            
            end = await clock.current_time()
            return f"{name} completed in {end - start:.1f}s"
        
        return Effect(impl)
    
    # Set up test environment
    scope = Scope()
    env = await TestClockLayer(test_clock).build_scoped(Context(), scope)
    
    # Fork tasks with different durations
    fiber1 = runtime.fork(timed_task(1.0, "Task1"))
    fiber2 = runtime.fork(timed_task(2.0, "Task2"))
    
    # Advance time and collect results
    await asyncio.sleep(0.01)  # Let tasks start
    
    test_clock.advance(1.0)  # Task1 should complete
    result1 = await fiber1.await_()
    print(f"After 1s: {result1}")
    
    test_clock.advance(1.0)  # Task2 should complete  
    result2 = await fiber2.await_()
    print(f"After 2s: {result2}")
    
    await runtime.shutdown()
    await scope.close()

asyncio.run(runtime_testing())
```

## Performance Considerations

### Fiber Overhead

```python
import asyncio
import time
from effectpy import *

async def performance_comparison():
    """Compare direct execution vs fiber execution"""
    
    def simple_task(task_id: int) -> Effect[Any, str, int]:
        async def impl(ctx: Context):
            await asyncio.sleep(0.001)  # Minimal work
            return task_id * 2
        return Effect(impl)
    
    num_tasks = 100
    
    # Direct execution
    start_time = time.time()
    direct_results = []
    for i in range(num_tasks):
        result = await simple_task(i)._run(Context())
        direct_results.append(result)
    direct_time = time.time() - start_time
    
    # Runtime with fibers
    runtime = Runtime()
    start_time = time.time()
    
    fibers = []
    for i in range(num_tasks):
        fiber = runtime.fork(simple_task(i))
        fibers.append(fiber)
    
    fiber_results = []
    for fiber in fibers:
        result = await fiber.await_()
        fiber_results.append(result)
    
    fiber_time = time.time() - start_time
    await runtime.shutdown()
    
    print(f"📊 Performance Comparison ({num_tasks} tasks):")
    print(f"  Direct execution: {direct_time:.3f}s")
    print(f"  Fiber execution:  {fiber_time:.3f}s")
    print(f"  Overhead: {((fiber_time - direct_time) / direct_time * 100):.1f}%")

asyncio.run(performance_comparison())
```

## Best Practices

### 1. Use Runtime for Concurrent Systems

```python
# ✅ Good: Runtime for managing multiple concurrent processes
async def good_concurrent_system():
    runtime = Runtime()
    
    # Multiple long-running services
    services = [
        ("WebServer", web_server_effect()),
        ("DatabaseCleanup", db_cleanup_effect()),
        ("MetricsCollector", metrics_effect())
    ]
    
    fibers = []
    for name, service in services:
        fiber = runtime.fork(service)
        fibers.append((name, fiber))
    
    # Handle shutdown gracefully
    # ... application logic ...
    
    for name, fiber in fibers:
        await fiber.interrupt()
    
    await runtime.shutdown()

# ❌ Avoid: Runtime for simple sequential operations
async def avoid_runtime_for_simple():
    runtime = Runtime()  # Unnecessary overhead
    
    result = await runtime.fork(succeed(42))  # Just use ._run(Context())
    await runtime.shutdown()
```

### 2. Always Clean Up Runtime

```python
# ✅ Good: Proper cleanup
async def proper_cleanup():
    runtime = Runtime()
    
    try:
        # Your application logic
        fiber = runtime.fork(my_effect())
        result = await fiber.await_()
        return result
    finally:
        await runtime.shutdown()  # Always cleanup

# ✅ Better: Use context manager if available
async def context_manager_cleanup():
    async with runtime_context() as runtime:
        fiber = runtime.fork(my_effect())
        return await fiber.await_()
```

### 3. Handle Fiber Failures Appropriately

```python
# ✅ Good: Handle fiber failures explicitly
async def handle_failures():
    runtime = Runtime()
    
    critical_fiber = runtime.fork(critical_service())
    optional_fiber = runtime.fork(optional_service())
    
    try:
        # Critical service must succeed
        await critical_fiber.await_()
        
        # Optional service can fail
        try:
            await optional_fiber.await_()
        except Exception as e:
            print(f"Optional service failed: {e}")
            
    finally:
        await runtime.shutdown()
```

### 4. Use Supervision for Resilience

```python
# ✅ Good: Supervise important long-running processes
class ServiceSupervisor:
    def __init__(self, runtime: Runtime):
        self.runtime = runtime
        
    def supervise(self, service_effect: Effect[Any, str, Any], name: str):
        def supervised():
            # Restart logic, health checks, etc.
            pass
        
        return self.runtime.fork(Effect(supervised))
```

## What's Next?

- :octicons-arrow-right-24: [Concurrency Guide](../guides/concurrency.md) - Practical concurrent programming patterns
- :octicons-arrow-right-24: [Effects](effects.md) - Understanding the Effect system
- :octicons-arrow-right-24: [Streams & Channels](streams_channels.md) - Concurrent data processing
- :octicons-arrow-right-24: [Runtime API Reference](../reference/runtime.md) - Complete API documentation

