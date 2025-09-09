# Observability

Observability is built into effectpy from the ground up. Unlike many async libraries where monitoring is an afterthought, effectpy makes it trivial to add comprehensive logging, metrics, and tracing to any effect.

The `instrument()` function automatically captures:
- **Structured logs** with correlation IDs and context
- **Metrics** for performance monitoring  
- **Traces** for distributed request tracking

## The Three Pillars

### 1. Logging

effectpy provides structured logging with automatic correlation IDs:

```python
import asyncio
from effectpy import *

async def user_service_example():
    scope = Scope()
    env = await LoggerLayer.build_scoped(Context(), scope)
    
    logger = env.get(ConsoleLogger)
    
    # Manual logging
    logger.info("User service starting", tags={"component": "user_service"})
    
    # Automatic logging via instrumentation
    def fetch_user(user_id: int) -> Effect[Any, str, dict]:
        return succeed({"id": user_id, "name": f"User {user_id}"})
    
    instrumented = instrument(
        "user.fetch",
        fetch_user(123),
        tags={"user_id": 123, "operation": "fetch"}
    )
    
    result = await instrumented._run(env)
    print(f"Result: {result}")
    
    await scope.close()

asyncio.run(user_service_example())
```

#### Log Formats

Choose between plain text and structured JSON:

```python
# Plain text logging (default)
# [2024-01-15 10:30:45] INFO [correlation_id=abc123] user.fetch started {user_id=123}

# JSON logging - better for log aggregation
logger = ConsoleLogger(json_output=True)
# {"timestamp": "2024-01-15T10:30:45Z", "level": "INFO", "message": "user.fetch started", "correlation_id": "abc123", "tags": {"user_id": 123}}
```

#### Correlation IDs

effectpy automatically tracks correlation IDs across async operations:

```python
async def correlation_example():
    scope = Scope()
    env = await LoggerLayer.build_scoped(Context(), scope)
    
    async def service_a() -> Effect[ConsoleLogger, str, str]:
        async def impl(ctx: Context):
            logger = ctx.get(ConsoleLogger)
            logger.info("Service A starting")
            
            # Call another service
            result = await service_b()._run(ctx)
            logger.info("Service A completed", tags={"result": result})
            return f"A -> {result}"
        
        return Effect(impl)
    
    async def service_b() -> Effect[ConsoleLogger, str, str]:
        async def impl(ctx: Context):
            logger = ctx.get(ConsoleLogger)
            logger.info("Service B processing")  # Same correlation ID
            return "B result"
        
        return Effect(impl)
    
    # All logs will share the same correlation ID
    result = await service_a()._run(env)
    print(f"Final result: {result}")
    
    await scope.close()

asyncio.run(correlation_example())
```

### 2. Metrics

effectpy includes a complete metrics system with counters, gauges, and histograms:

```python
import asyncio
from effectpy import *

async def metrics_example():
    scope = Scope()
    env = await (LoggerLayer | MetricsLayer).build_scoped(Context(), scope)
    
    metrics = env.get(MetricsRegistry)
    
    # Create metrics
    request_counter = metrics.counter("http_requests_total", "Total HTTP requests")
    response_time = metrics.histogram("http_response_time_seconds", "HTTP response time")
    active_connections = metrics.gauge("http_active_connections", "Active HTTP connections")
    
    # Manual metrics
    request_counter.inc(labels={"method": "GET", "endpoint": "/users"})
    active_connections.set(42, labels={"server": "web-01"})
    
    with response_time.time(labels={"method": "GET"}):
        await asyncio.sleep(0.1)  # Simulate request processing
    
    # Automatic metrics via instrumentation  
    def api_call() -> Effect[Any, str, dict]:
        return succeed({"status": "success", "data": "API response"})
    
    instrumented = instrument(
        "api.call",
        api_call(),
        tags={"method": "GET", "endpoint": "/api/data"}
    )
    
    result = await instrumented._run(env)
    
    # Print collected metrics
    print("Collected metrics:")
    for metric in metrics.collect():
        print(f"  {metric.name}: {metric.value} {metric.labels}")
    
    await scope.close()

asyncio.run(metrics_example())
```

### 3. Tracing

Distributed tracing helps you understand request flows across services:

```python
import asyncio
from effectpy import *

async def tracing_example():
    scope = Scope()
    env = await (LoggerLayer | TracerLayer).build_scoped(Context(), scope)
    
    tracer = env.get(Tracer)
    
    # Manual span creation
    with tracer.span("database.query", attributes={"table": "users", "query": "SELECT *"}) as span:
        await asyncio.sleep(0.05)  # Simulate DB query
        span.add_event("query_executed", {"rows_returned": 10})
    
    # Automatic tracing via instrumentation
    def complex_operation() -> Effect[Any, str, str]:
        async def impl(ctx: Context):
            # Nested operation - creates child span
            await asyncio.sleep(0.02)
            
            nested = instrument(
                "complex.nested",
                succeed("nested result"),
                tags={"step": "processing"}
            )
            
            nested_result = await nested._run(ctx)
            return f"Complex: {nested_result}"
        
        return Effect(impl)
    
    instrumented = instrument(
        "complex.operation",
        complex_operation(),
        tags={"request_id": "req-123", "user_id": 456}
    )
    
    result = await instrumented._run(env)
    print(f"Result: {result}")
    
    # Export traces
    spans = tracer.get_spans()
    for span in spans:
        print(f"Span: {span.name} ({span.duration:.3f}s)")
        for event in span.events:
            print(f"  Event: {event.name} - {event.attributes}")
    
    await scope.close()

asyncio.run(tracing_example())
```

## The instrument() Function

The `instrument()` function is the primary way to add observability to effects:

```python
from effectpy import *

# Basic instrumentation
instrumented_effect = instrument("operation.name", my_effect)

# With tags for context
instrumented_effect = instrument(
    "user.fetch",
    fetch_user_effect,
    tags={
        "user_id": 123,
        "source": "database",
        "cache": "enabled"
    }
)

# Tags can be dynamic
def fetch_with_dynamic_tags(user_id: int) -> Effect[Any, str, dict]:
    base_effect = fetch_user(user_id)
    
    return instrument(
        "user.fetch",
        base_effect,
        tags={
            "user_id": user_id,
            "timestamp": int(time.time()),
            "environment": "production"
        }
    )
```

### What instrument() Captures

For every instrumented effect, effectpy automatically records:

1. **Start/End Events**: When the operation begins and completes
2. **Duration**: How long the operation took
3. **Success/Failure**: Whether the operation succeeded or failed
4. **Error Details**: Full error information if it failed
5. **Tags**: All provided metadata
6. **Correlation ID**: Automatic request tracking

## OpenTelemetry Integration

effectpy supports OpenTelemetry Protocol (OTLP) for integration with observability platforms:

```python
import asyncio
from effectpy import *

async def otlp_export_example():
    scope = Scope()
    env = await (LoggerLayer | MetricsLayer | TracerLayer).build_scoped(Context(), scope)
    
    # Your instrumented application code
    def api_workflow() -> Effect[Any, str, dict]:
        auth_check = instrument("auth.check", succeed({"user": "alice"}))
        
        data_fetch = instrument(
            "data.fetch", 
            succeed({"records": [1, 2, 3]}),
            tags={"table": "users", "limit": 100}
        )
        
        return (
            auth_check
            .flat_map(lambda auth: data_fetch)
            .map(lambda data: {"auth": auth, "data": data})
        )
    
    # Run workflow
    result = await instrument("api.workflow", api_workflow())._run(env)
    
    # Export to OpenTelemetry collectors
    tracer = env.get(Tracer)
    metrics = env.get(MetricsRegistry)
    
    # Export spans (requires aiohttp)
    await export_spans_otlp_http(
        spans=tracer.get_spans(),
        endpoint="http://jaeger:14268/api/traces"
    )
    
    # Export metrics (requires aiohttp)  
    await export_metrics_otlp_http(
        metrics=metrics.collect(),
        endpoint="http://prometheus:9090/api/v1/otlp/metrics"
    )
    
    print(f"Workflow completed: {result}")
    await scope.close()

# Only runs if aiohttp is available
try:
    asyncio.run(otlp_export_example())
except ImportError:
    print("aiohttp not available - OTLP export skipped")
```

## Real-World Patterns

### API Request Tracing

```python
import asyncio
from effectpy import *

class HTTPClient:
    async def get(self, url: str) -> dict:
        await asyncio.sleep(0.1)  # Simulate network call
        return {"status": 200, "data": f"Response from {url}"}

async def api_request_tracing():
    scope = Scope()
    env = await (LoggerLayer | MetricsLayer | TracerLayer).build_scoped(Context(), scope)
    
    # Add HTTP client to environment
    http_client = HTTPClient()
    env = env.with_service(HTTPClient, http_client)
    
    def make_request(url: str) -> Effect[HTTPClient, str, dict]:
        async def impl(ctx: Context):
            client = ctx.get(HTTPClient)
            response = await client.get(url)
            
            if response["status"] >= 400:
                raise ValueError(f"HTTP {response['status']}")
            
            return response
        
        return Effect(impl)
    
    # Instrument the request with rich context
    instrumented_request = instrument(
        "http.request",
        make_request("https://api.example.com/users"),
        tags={
            "method": "GET",
            "url": "https://api.example.com/users",
            "service": "user-api",
            "version": "1.2.3"
        }
    )
    
    result = await instrumented_request._run(env)
    print(f"API Response: {result}")
    
    await scope.close()

asyncio.run(api_request_tracing())
```

### Database Query Monitoring

```python
async def database_monitoring():
    scope = Scope()
    env = await (LoggerLayer | MetricsLayer | TracerLayer).build_scoped(Context(), scope)
    
    class Database:
        async def query(self, sql: str) -> list:
            # Simulate query execution time based on complexity
            if "JOIN" in sql.upper():
                await asyncio.sleep(0.2)  # Complex query
            else:
                await asyncio.sleep(0.05)  # Simple query
            
            return [{"id": 1, "name": "Alice"}]
    
    db = Database()
    env = env.with_service(Database, db)
    
    def execute_query(sql: str) -> Effect[Database, str, list]:
        async def impl(ctx: Context):
            database = ctx.get(Database)
            return await database.query(sql)
        
        return Effect(impl)
    
    # Different query types with different tags
    queries = [
        ("SELECT * FROM users", "simple"),
        ("SELECT u.*, p.* FROM users u JOIN profiles p ON u.id = p.user_id", "complex"),
        ("SELECT COUNT(*) FROM users", "aggregate")
    ]
    
    for sql, query_type in queries:
        instrumented_query = instrument(
            "database.query",
            execute_query(sql),
            tags={
                "query_type": query_type,
                "table": "users",
                "operation": sql.split()[0].upper()  # SELECT, INSERT, etc.
            }
        )
        
        result = await instrumented_query._run(env)
        print(f"{query_type.capitalize()} query returned {len(result)} rows")
    
    # Print performance metrics
    metrics = env.get(MetricsRegistry)
    print("\nDatabase metrics:")
    for metric in metrics.collect():
        if "database" in metric.name:
            print(f"  {metric.name}: {metric.value}")
    
    await scope.close()

asyncio.run(database_monitoring())
```

### Error Tracking

```python
async def error_tracking_example():
    scope = Scope()
    env = await (LoggerLayer | MetricsLayer | TracerLayer).build_scoped(Context(), scope)
    
    def unreliable_service(failure_rate: float) -> Effect[Any, str, str]:
        import random
        if random.random() < failure_rate:
            return fail(f"Service failed (rate: {failure_rate})")
        return succeed("Service success")
    
    # Test different failure scenarios
    scenarios = [
        ("reliable", 0.1),    # 10% failure
        ("unreliable", 0.7),  # 70% failure  
        ("broken", 1.0)       # 100% failure
    ]
    
    for name, failure_rate in scenarios:
        for attempt in range(5):
            instrumented = instrument(
                "service.call",
                unreliable_service(failure_rate),
                tags={
                    "service": name,
                    "attempt": attempt + 1,
                    "failure_rate": failure_rate
                }
            )
            
            try:
                result = await instrumented._run(env)
                print(f"{name} attempt {attempt + 1}: SUCCESS")
            except Failure as f:
                print(f"{name} attempt {attempt + 1}: FAILED - {f.error}")
    
    # Analyze error patterns
    metrics = env.get(MetricsRegistry)
    tracer = env.get(Tracer)
    
    print(f"\nCaptured {len(tracer.get_spans())} spans")
    
    # Group spans by outcome
    successes = [s for s in tracer.get_spans() if s.status == "ok"]
    failures = [s for s in tracer.get_spans() if s.status == "error"]
    
    print(f"Successes: {len(successes)}")
    print(f"Failures: {len(failures)}")
    
    if failures:
        print("Failure breakdown:")
        failure_services = {}
        for span in failures:
            service = span.tags.get("service", "unknown")
            failure_services[service] = failure_services.get(service, 0) + 1
        
        for service, count in failure_services.items():
            print(f"  {service}: {count} failures")
    
    await scope.close()

asyncio.run(error_tracking_example())
```

## Best Practices

### 1. Use Meaningful Names

```python
# ✅ Good: Clear, hierarchical names
instrument("user.profile.fetch", fetch_profile_effect)
instrument("payment.stripe.charge", charge_payment_effect)
instrument("cache.redis.get", get_from_cache_effect)

# ❌ Avoid: Vague or inconsistent names  
instrument("operation", some_effect)
instrument("getUserProfile", fetch_profile_effect)  # inconsistent naming
```

### 2. Add Rich Context with Tags

```python
# ✅ Good: Rich, searchable tags
instrument(
    "database.query",
    query_effect,
    tags={
        "table": "users",
        "operation": "SELECT", 
        "user_id": 123,
        "query_type": "user_lookup",
        "cache_enabled": True
    }
)

# ❌ Avoid: Missing context
instrument("db", query_effect)  # No useful metadata
```

### 3. Instrument at the Right Level

```python
# ✅ Good: Instrument meaningful business operations
def process_user_registration(user_data: dict) -> Effect[Any, str, dict]:
    validate = instrument("user.validate", validate_user_data(user_data))
    create = instrument("user.create", create_user_in_db(user_data))
    notify = instrument("user.notify", send_welcome_email(user_data))
    
    return validate.flat_map(lambda _: create).flat_map(lambda user: notify.map(lambda _: user))

# ❌ Avoid: Over-instrumenting trivial operations
instrument("string.format", succeed(f"Hello {name}"))  # Too granular
```

### 4. Handle Observability Layer Failures

```python
async def robust_observability():
    scope = Scope()
    
    try:
        # Build observability environment
        env = await (LoggerLayer | MetricsLayer | TracerLayer).build_scoped(Context(), scope)
        
        # Your application code
        result = await instrument("app.main", main_workflow())._run(env)
        
    except Exception as e:
        # Observability setup failed - run without it
        print(f"Observability unavailable: {e}")
        result = await main_workflow()._run(Context())
    
    finally:
        await scope.close()
    
    return result
```

## Integration Examples

### Prometheus Metrics

```python
# Export effectpy metrics to Prometheus format
async def prometheus_integration():
    scope = Scope()
    env = await MetricsLayer.build_scoped(Context(), scope)
    
    # Run your instrumented application
    await my_instrumented_app()._run(env)
    
    # Export metrics in Prometheus format
    metrics = env.get(MetricsRegistry)
    prometheus_output = []
    
    for metric in metrics.collect():
        labels = ",".join(f'{k}="{v}"' for k, v in metric.labels.items())
        prometheus_output.append(f"{metric.name}{{{labels}}} {metric.value}")
    
    print("# Prometheus Metrics")
    for line in prometheus_output:
        print(line)
    
    await scope.close()
```

### Jaeger Tracing

```python
async def jaeger_integration():
    scope = Scope()
    env = await TracerLayer.build_scoped(Context(), scope)
    
    # Run traced application
    await my_traced_app()._run(env)
    
    # Export to Jaeger (if aiohttp available)
    tracer = env.get(Tracer)
    spans = tracer.get_spans()
    
    try:
        await export_spans_otlp_http(
            spans,
            endpoint="http://jaeger:14268/api/traces"
        )
        print(f"Exported {len(spans)} spans to Jaeger")
    except ImportError:
        print("aiohttp not available - Jaeger export skipped")
    except Exception as e:
        print(f"Failed to export spans: {e}")
    
    await scope.close()
```

## What's Next?

- :octicons-arrow-right-24: [Effects](effects.md) - Learn how to instrument your effects
- :octicons-arrow-right-24: [Layers & Scope](layers_scope.md) - Set up observability environments  
- :octicons-arrow-right-24: [Concurrency Guide](../guides/concurrency.md) - Monitoring concurrent operations
- :octicons-arrow-right-24: [Observability API Reference](../reference/observability.md) - Complete API documentation

