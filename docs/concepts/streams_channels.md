# Streams & Channels

Streams and channels in effectpy provide powerful, composable abstractions for async data processing. They enable you to build robust data pipelines with backpressure, error handling, and parallel processing.

**Key components:**
- **Channel**: Async communication primitive with backpressure
- **Stream**: Functional data streams for transformation pipelines  
- **StreamE**: Error-aware streams with failure channels
- **Pipeline**: Multi-stage data processing with parallel workers

## Channels: Async Communication

Channels are effectpy's core communication primitive - think of them as async queues with built-in backpressure and proper resource management.

### Basic Channel Usage

```python
import asyncio
from effectpy import *

async def channel_basics():
    # Create a channel with buffer size 3
    channel = Channel[str](maxsize=3)
    
    async def producer():
        for i in range(5):
            message = f"Message {i+1}"
            print(f"📤 Sending: {message}")
            await channel.send(message)
            await asyncio.sleep(0.1)
        
        # Signal completion
        await channel.close()
        print("📤 Producer finished")
    
    async def consumer():
        print("📥 Consumer started")
        try:
            while True:
                message = await channel.receive()
                print(f"📥 Received: {message}")
                await asyncio.sleep(0.2)  # Slower than producer
        except ChannelClosed:
            print("📥 Consumer finished (channel closed)")
    
    # Run producer and consumer concurrently
    await asyncio.gather(producer(), consumer())

asyncio.run(channel_basics())
```

### Backpressure in Action

```python
import asyncio
from effectpy import *

async def backpressure_demo():
    # Small buffer to demonstrate backpressure
    channel = Channel[int](maxsize=2)
    
    async def fast_producer():
        for i in range(10):
            print(f"⚡ Producer trying to send {i}")
            await channel.send(i)  # Will block when buffer is full
            print(f"✅ Sent {i}")
    
    async def slow_consumer():
        await asyncio.sleep(1.0)  # Start after producer builds up
        
        for i in range(10):
            await asyncio.sleep(0.5)  # Slow consumption
            value = await channel.receive()
            print(f"🐌 Consumer received {value}")
    
    await asyncio.gather(fast_producer(), slow_consumer())

asyncio.run(backpressure_demo())
```

## Streams: Functional Data Processing

Streams provide functional programming abstractions for data transformation:

### Stream Basics

```python
import asyncio
from effectpy import *

async def stream_basics():
    # Create a stream from a range
    numbers = Stream.range(1, 6)  # 1, 2, 3, 4, 5
    
    # Transform the stream
    processed = (numbers
                 .map(lambda x: x * 2)           # Double each number
                 .filter(lambda x: x > 5)        # Keep only > 5
                 .map(lambda x: f"Result: {x}")  # Format as string
                )
    
    # Collect results
    results = await processed.run_collect()
    print(f"Stream results: {results}")
    
    # Alternative: process one by one
    async for item in processed.run():
        print(f"Streaming: {item}")

asyncio.run(stream_basics())
```

### Stream from Channels

```python
import asyncio
from effectpy import *

async def stream_from_channel():
    channel = Channel[int](maxsize=5)
    
    # Producer fills the channel
    async def produce_data():
        for i in range(1, 11):
            await channel.send(i)
            await asyncio.sleep(0.1)
        await channel.close()
    
    # Create stream from channel
    stream = Stream.from_channel(channel)
    
    # Process stream with transformations
    processed = (stream
                 .map(lambda x: x ** 2)               # Square numbers
                 .filter(lambda x: x % 2 == 0)        # Even squares only
                 .take(5)                             # Take first 5
                )
    
    # Start producer
    producer_task = asyncio.create_task(produce_data())
    
    # Process stream
    results = []
    async for value in processed.run():
        results.append(value)
        print(f"Processed: {value}")
    
    await producer_task
    print(f"Final results: {results}")

asyncio.run(stream_from_channel())
```

## StreamE: Error-Aware Streams

StreamE adds error handling to streams, allowing you to separate successful values from failures:

### StreamE with Error Handling

```python
import asyncio
from effectpy import *

async def stream_with_errors():
    def risky_operation(x: int) -> Effect[Any, str, int]:
        if x % 3 == 0:  # Fail on multiples of 3
            return fail(f"Error processing {x}")
        return succeed(x * 2)
    
    # Create StreamE from range
    stream = StreamE.range(1, 10)  # 1 through 9
    
    # Apply risky operation
    processed = stream.map_effect(risky_operation)
    
    # Separate successes and failures
    successes = []
    failures = []
    
    async for result in processed.run():
        match result:
            case Ok(value):
                successes.append(value)
                print(f"✅ Success: {value}")
            case Err(error):
                failures.append(error)
                print(f"❌ Error: {error}")
    
    print(f"\nSummary:")
    print(f"  Successes: {successes}")
    print(f"  Failures: {failures}")

asyncio.run(stream_with_errors())
```

### Error Recovery in Streams

```python
import asyncio
from effectpy import *

async def stream_error_recovery():
    def unreliable_network_call(url: str) -> Effect[Any, str, dict]:
        import random
        if random.random() < 0.4:  # 40% failure rate
            return fail(f"Network error for {url}")
        return succeed({"url": url, "status": 200, "data": f"Content from {url}"})
    
    urls = [f"https://api.example.com/data/{i}" for i in range(1, 8)]
    
    # Process URLs with error recovery
    stream = (StreamE.from_iterable(urls)
              .map_effect(unreliable_network_call)
              .map_error(lambda error: f"Handled: {error}")  # Transform errors
              .recover(lambda error: succeed({"url": "fallback", "error": error}))  # Provide fallback
             )
    
    results = []
    async for result in stream.run():
        results.append(result)
        print(f"📊 Result: {result}")
    
    # Analyze results
    successful = [r for r in results if isinstance(r.value, dict) and r.value.get("status") == 200]
    recovered = [r for r in results if isinstance(r.value, dict) and "error" in r.value]
    
    print(f"\n📈 Analysis:")
    print(f"  Successful calls: {len(successful)}")
    print(f"  Recovered calls: {len(recovered)}")

asyncio.run(stream_error_recovery())
```

## Pipelines: Multi-Stage Processing

Pipelines provide structured, parallel data processing with multiple stages:

### Basic Pipeline

```python
import asyncio
from effectpy import *

async def basic_pipeline():
    # Input and output channels
    input_channel = Channel[int](maxsize=10)
    output_channel = Channel[str](maxsize=10)
    
    # Pipeline stages
    async def stage1(x: int) -> int:
        """Double the input"""
        await asyncio.sleep(0.1)  # Simulate work
        return x * 2
    
    async def stage2(x: int) -> str:
        """Format as string"""
        await asyncio.sleep(0.05)  # Different processing time
        return f"Processed: {x}"
    
    # Create pipeline
    pipeline = (Pipeline.from_channel(input_channel)
                .via(stage(stage1, workers=2))    # 2 parallel workers
                .via(stage(stage2, workers=3))    # 3 parallel workers  
                .to_channel(output_channel)
               )
    
    async def producer():
        for i in range(1, 11):
            await input_channel.send(i)
            print(f"📤 Input: {i}")
        await input_channel.close()
    
    async def consumer():
        results = []
        try:
            while True:
                result = await output_channel.receive()
                results.append(result)
                print(f"📥 Output: {result}")
        except ChannelClosed:
            print(f"🏁 Completed! Processed {len(results)} items")
    
    # Run everything concurrently
    await asyncio.gather(
        producer(),
        pipeline.run(),
        consumer()
    )

asyncio.run(basic_pipeline())
```

### Pipeline with Error Handling

```python
import asyncio
from effectpy import *

async def pipeline_with_errors():
    input_channel = Channel[int](maxsize=5)
    success_channel = Channel[str](maxsize=5)
    error_channel = Channel[str](maxsize=5)
    
    async def validate_stage(x: int) -> int:
        """Validation stage - rejects negative numbers"""
        if x < 0:
            raise ValueError(f"Negative number: {x}")
        return x
    
    async def process_stage(x: int) -> str:
        """Processing stage - fails on multiples of 7"""
        await asyncio.sleep(0.1)
        if x % 7 == 0:
            raise ValueError(f"Cannot process multiple of 7: {x}")
        return f"Processed: {x}"
    
    # Pipeline with error channels
    pipeline = (Pipeline.from_channel(input_channel)
                .via(stage(validate_stage, workers=2))
                .via(stage(process_stage, workers=2))
                .to_channel(success_channel)
                .with_error_channel(error_channel)
               )
    
    async def producer():
        test_data = [-5, 1, 2, 7, -3, 4, 14, 5, 6, 8]
        for value in test_data:
            await input_channel.send(value)
            print(f"📤 Sent: {value}")
        await input_channel.close()
    
    async def success_consumer():
        successes = []
        try:
            while True:
                result = await success_channel.receive()
                successes.append(result)
                print(f"✅ Success: {result}")
        except ChannelClosed:
            print(f"✅ Success consumer finished: {len(successes)} items")
    
    async def error_consumer():
        errors = []
        try:
            while True:
                error = await error_channel.receive()
                errors.append(error)
                print(f"❌ Error: {error}")
        except ChannelClosed:
            print(f"❌ Error consumer finished: {len(errors)} errors")
    
    await asyncio.gather(
        producer(),
        pipeline.run(),
        success_consumer(),
        error_consumer()
    )

asyncio.run(pipeline_with_errors())
```

## Real-World Patterns

### Data Processing Pipeline

```python
import asyncio
import json
from dataclasses import dataclass
from typing import List, Dict, Any
from effectpy import *

@dataclass
class WebEvent:
    timestamp: float
    user_id: str
    event_type: str
    data: Dict[str, Any]

@dataclass  
class ProcessedEvent:
    user_id: str
    event_type: str
    processed_at: float
    enriched_data: Dict[str, Any]

async def data_processing_pipeline():
    # Simulated data source
    raw_events = [
        {"timestamp": 1634567890, "user_id": "user1", "event_type": "click", "data": {"page": "home"}},
        {"timestamp": 1634567891, "user_id": "user2", "event_type": "purchase", "data": {"amount": 29.99}},
        {"timestamp": 1634567892, "user_id": "user1", "event_type": "view", "data": {"page": "products"}},
        {"timestamp": 1634567893, "user_id": "user3", "event_type": "click", "data": {"page": "about"}},
        {"timestamp": 1634567894, "user_id": "user2", "event_type": "purchase", "data": {"amount": 15.99}},
    ]
    
    input_channel = Channel[Dict[str, Any]](maxsize=10)
    output_channel = Channel[ProcessedEvent](maxsize=10)
    
    # Pipeline stages
    async def parse_stage(raw: Dict[str, Any]) -> WebEvent:
        """Parse raw JSON into structured event"""
        await asyncio.sleep(0.01)  # Simulate parsing time
        return WebEvent(
            timestamp=raw["timestamp"],
            user_id=raw["user_id"],
            event_type=raw["event_type"],
            data=raw["data"]
        )
    
    async def validate_stage(event: WebEvent) -> WebEvent:
        """Validate event data"""
        if not event.user_id or not event.event_type:
            raise ValueError(f"Invalid event: missing user_id or event_type")
        return event
    
    async def enrich_stage(event: WebEvent) -> WebEvent:
        """Enrich event with additional data"""
        await asyncio.sleep(0.02)  # Simulate database lookup
        
        # Add user segment info (simulated)
        user_segments = {
            "user1": "premium",
            "user2": "standard", 
            "user3": "new"
        }
        
        enriched_data = {
            **event.data,
            "user_segment": user_segments.get(event.user_id, "unknown"),
            "processing_pipeline": "v1.0"
        }
        
        return WebEvent(
            timestamp=event.timestamp,
            user_id=event.user_id,
            event_type=event.event_type,
            data=enriched_data
        )
    
    async def transform_stage(event: WebEvent) -> ProcessedEvent:
        """Transform to final output format"""
        import time
        return ProcessedEvent(
            user_id=event.user_id,
            event_type=event.event_type,
            processed_at=time.time(),
            enriched_data=event.data
        )
    
    # Build pipeline
    pipeline = (Pipeline.from_channel(input_channel)
                .via(stage(parse_stage, workers=2))
                .via(stage(validate_stage, workers=1))     # Single validator
                .via(stage(enrich_stage, workers=3))       # Parallel enrichment
                .via(stage(transform_stage, workers=2))
                .to_channel(output_channel)
               )
    
    async def producer():
        print("📡 Starting event ingestion...")
        for event in raw_events:
            await input_channel.send(event)
            print(f"📤 Ingested: {event['event_type']} from {event['user_id']}")
            await asyncio.sleep(0.1)
        
        await input_channel.close()
        print("📡 Ingestion completed")
    
    async def consumer():
        processed_events = []
        try:
            while True:
                event = await output_channel.receive()
                processed_events.append(event)
                print(f"📊 Processed: {event.event_type} for {event.user_id} "
                      f"(segment: {event.enriched_data.get('user_segment', 'unknown')})")
        except ChannelClosed:
            print(f"\n📈 Pipeline Summary:")
            print(f"  Total events processed: {len(processed_events)}")
            
            # Group by event type
            by_type = {}
            for event in processed_events:
                by_type[event.event_type] = by_type.get(event.event_type, 0) + 1
            
            print(f"  Events by type: {by_type}")
    
    # Run pipeline
    await asyncio.gather(
        producer(),
        pipeline.run(),
        consumer()
    )

asyncio.run(data_processing_pipeline())
```

### Stream Processing with Windowing

```python
import asyncio
import time
from collections import deque
from dataclasses import dataclass
from typing import List
from effectpy import *

@dataclass
class Metric:
    timestamp: float
    value: float
    source: str

@dataclass
class WindowedResult:
    window_start: float
    window_end: float
    count: int
    avg_value: float
    max_value: float
    sources: List[str]

class SlidingWindow:
    def __init__(self, window_size: float):
        self.window_size = window_size
        self.metrics = deque()
    
    def add_metric(self, metric: Metric) -> List[Metric]:
        """Add metric and return current window"""
        self.metrics.append(metric)
        
        # Remove old metrics outside window
        cutoff = metric.timestamp - self.window_size
        while self.metrics and self.metrics[0].timestamp < cutoff:
            self.metrics.popleft()
        
        return list(self.metrics)
    
    def compute_window_stats(self, metrics: List[Metric]) -> WindowedResult:
        """Compute statistics for current window"""
        if not metrics:
            return WindowedResult(0, 0, 0, 0, 0, [])
        
        values = [m.value for m in metrics]
        sources = list(set(m.source for m in metrics))
        
        return WindowedResult(
            window_start=min(m.timestamp for m in metrics),
            window_end=max(m.timestamp for m in metrics),
            count=len(metrics),
            avg_value=sum(values) / len(values),
            max_value=max(values),
            sources=sources
        )

async def windowed_stream_processing():
    """Process a stream of metrics with sliding window aggregation"""
    
    # Generate simulated metrics
    def generate_metrics():
        import random
        sources = ["server1", "server2", "server3"]
        base_time = time.time()
        
        metrics = []
        for i in range(50):
            metrics.append(Metric(
                timestamp=base_time + i * 0.2,  # Every 200ms
                value=random.uniform(10, 100),
                source=random.choice(sources)
            ))
        return metrics
    
    metrics = generate_metrics()
    input_channel = Channel[Metric](maxsize=10)
    output_channel = Channel[WindowedResult](maxsize=10)
    
    # Windowing stage
    window = SlidingWindow(window_size=2.0)  # 2 second window
    
    async def windowing_stage(metric: Metric) -> WindowedResult:
        """Apply sliding window and compute stats"""
        await asyncio.sleep(0.01)  # Simulate processing time
        
        current_window = window.add_metric(metric)
        return window.compute_window_stats(current_window)
    
    async def alerting_stage(result: WindowedResult) -> WindowedResult:
        """Check for alerts based on windowed data"""
        if result.avg_value > 75 and result.count >= 5:
            print(f"🚨 ALERT: High average value {result.avg_value:.1f} "
                  f"across {result.count} metrics")
        
        return result
    
    # Build pipeline
    pipeline = (Pipeline.from_channel(input_channel)
                .via(stage(windowing_stage, workers=1))    # Single window processor
                .via(stage(alerting_stage, workers=1))     # Single alerting processor
                .to_channel(output_channel)
               )
    
    async def producer():
        print("📊 Starting metric stream...")
        for metric in metrics:
            await input_channel.send(metric)
            print(f"📤 Metric: {metric.source} = {metric.value:.1f}")
            await asyncio.sleep(0.1)  # Slower than metric timestamps
        
        await input_channel.close()
    
    async def consumer():
        window_results = []
        try:
            while True:
                result = await output_channel.receive()
                window_results.append(result)
                print(f"📈 Window [{result.window_start:.1f}-{result.window_end:.1f}]: "
                      f"count={result.count}, avg={result.avg_value:.1f}, "
                      f"max={result.max_value:.1f}")
        except ChannelClosed:
            print(f"\n📊 Window Processing Complete:")
            print(f"  Total windows: {len(window_results)}")
            
            if window_results:
                overall_avg = sum(r.avg_value for r in window_results) / len(window_results)
                overall_max = max(r.max_value for r in window_results)
                print(f"  Overall average: {overall_avg:.1f}")
                print(f"  Overall maximum: {overall_max:.1f}")
    
    await asyncio.gather(
        producer(),
        pipeline.run(),
        consumer()
    )

asyncio.run(windowed_stream_processing())
```

## Testing Streams and Pipelines

### Testing with Controlled Data

```python
import asyncio
from effectpy import *

async def test_stream_processing():
    """Test stream processing with known data"""
    
    # Test data
    test_numbers = [1, 2, 3, 4, 5, -1, 6, 7, 0, 8, 9, 10]
    
    def safe_divide_by_two(x: int) -> Effect[Any, str, float]:
        if x == 0:
            return fail("Division by zero")
        if x < 0:
            return fail(f"Negative number: {x}")
        return succeed(x / 2.0)
    
    # Test StreamE processing
    stream = (StreamE.from_iterable(test_numbers)
              .map_effect(safe_divide_by_two)
              .map(lambda result: result.map(lambda x: round(x, 1)))  # Round to 1 decimal
             )
    
    results = []
    errors = []
    
    async for result in stream.run():
        match result:
            case Ok(value):
                results.append(value)
            case Err(error):
                errors.append(error)
    
    print(f"✅ Successful results: {results}")
    print(f"❌ Errors: {errors}")
    
    # Assertions for testing
    assert len(results) == 9  # 12 inputs - 3 errors
    assert len(errors) == 3   # 2 negative + 1 zero
    assert 0.5 in results     # 1/2
    assert 5.0 in results     # 10/2
    
    print("🧪 All tests passed!")

asyncio.run(test_stream_processing())
```

## Best Practices

### 1. Use Appropriate Buffer Sizes

```python
# ✅ Good: Buffer size matches your use case
fast_producer_slow_consumer = Channel[int](maxsize=100)  # Larger buffer
balanced_processing = Channel[int](maxsize=10)           # Moderate buffer
real_time_processing = Channel[int](maxsize=1)           # Minimal buffering

# ❌ Avoid: Inappropriate buffer sizes
unlimited_memory_growth = Channel[int](maxsize=-1)       # Unbounded - memory risk
too_small_for_burst = Channel[int](maxsize=1)           # May cause deadlock
```

### 2. Handle Resource Cleanup

```python
# ✅ Good: Always close channels
async def proper_channel_usage():
    channel = Channel[str](maxsize=5)
    
    try:
        # Use channel
        await channel.send("data")
        result = await channel.receive()
    finally:
        await channel.close()  # Always cleanup

# ✅ Better: Use context managers when available
async def context_manager_usage():
    async with channel_context(maxsize=5) as channel:
        await channel.send("data")
        return await channel.receive()
    # Automatic cleanup
```

### 3. Design for Error Recovery

```python
# ✅ Good: Separate error handling
async def robust_pipeline():
    pipeline = (Pipeline.from_channel(input_channel)
                .via(stage(risky_operation, workers=2))
                .to_channel(success_channel)
                .with_error_channel(error_channel)  # Separate error handling
               )
    
    # Handle errors separately
    async def handle_errors():
        try:
            while True:
                error = await error_channel.receive()
                # Log, retry, or handle error appropriately
                logger.error(f"Pipeline error: {error}")
        except ChannelClosed:
            pass
```

### 4. Monitor Pipeline Performance

```python
# ✅ Good: Add monitoring to pipelines
class PipelineMonitor:
    def __init__(self):
        self.processed_count = 0
        self.error_count = 0
        self.start_time = time.time()
    
    async def monitored_stage(self, data):
        try:
            result = await process_data(data)
            self.processed_count += 1
            return result
        except Exception as e:
            self.error_count += 1
            raise
    
    def get_stats(self):
        elapsed = time.time() - self.start_time
        return {
            "processed": self.processed_count,
            "errors": self.error_count,
            "rate": self.processed_count / elapsed if elapsed > 0 else 0
        }
```

## What's Next?

- **→ [Concurrency Guide](../guides/concurrency.md)** - Advanced concurrent programming patterns
- **→ [Effects](effects.md)** - Understanding the Effect system that powers streams
- **→ [Runtime & Fibers](runtime_fibers.md)** - Concurrent execution fundamentals  
- **→ [Stream API Reference](../reference/stream.md)** - Complete streaming API documentation

