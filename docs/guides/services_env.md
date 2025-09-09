# Services & Environment Guide

Service-oriented architecture is a powerful pattern for building maintainable, testable applications. effectpy provides elegant service management through dependency injection, making it easy to compose complex environments while keeping your code modular and testable.

## Understanding Services

Services in effectpy represent dependencies that your effects need to run. Instead of passing dependencies explicitly through function parameters, effectpy uses the type system to automatically inject the right services.

### Basic Service Usage

```python
import asyncio
from effectpy import *

# Define services
class Logger:
    def log(self, message: str):
        print(f"[LOG] {message}")

class Database:
    async def query(self, sql: str) -> list:
        # Simulate database query
        await asyncio.sleep(0.1)
        return [{"id": 1, "name": "Alice"}]

# Service-aware effect
def fetch_user(user_id: int) -> Effect[Logger | Database, str, dict]:
    async def impl(ctx: Context):
        logger = ctx.get(Logger)
        db = ctx.get(Database)
        
        logger.log(f"Fetching user {user_id}")
        
        try:
            results = await db.query(f"SELECT * FROM users WHERE id = {user_id}")
            if not results:
                return {"error": "User not found"}
            
            user = results[0]
            logger.log(f"Found user: {user['name']}")
            return user
        
        except Exception as e:
            logger.log(f"Database error: {e}")
            raise
    
    return Effect(impl)

async def basic_services_example():
    # Build environment with services
    ctx = (Context()
           .with_service(Logger, Logger())
           .with_service(Database, Database()))
    
    # Use the effect
    result = await fetch_user(1)._run(ctx)
    print(f"Result: {result}")

asyncio.run(basic_services_example())
```

## Service Helpers

effectpy provides convenient helpers for working with services:

### service() Function

```python
import asyncio
from effectpy import *

class ConfigService:
    def __init__(self):
        self.api_url = "https://api.example.com"
        self.timeout = 30
        self.retries = 3

# Access service using helper
def get_api_config() -> Effect[ConfigService, None, dict]:
    return service(ConfigService).map(lambda config: {
        "url": config.api_url,
        "timeout": config.timeout,
        "retries": config.retries
    })

async def service_helper_example():
    config_service = ConfigService()
    ctx = Context().with_service(ConfigService, config_service)
    
    config = await get_api_config()._run(ctx)
    print(f"API Config: {config}")

asyncio.run(service_helper_example())
```

### provide_service() Layer

```python
import asyncio
from effectpy import *

class MetricsCollector:
    def __init__(self):
        self.metrics = {}
    
    def record(self, name: str, value: float):
        self.metrics[name] = self.metrics.get(name, 0) + value
        print(f"📊 {name}: {value} (total: {self.metrics[name]})")

# Create service layer
MetricsLayer = provide_service(MetricsCollector, MetricsCollector())

async def provide_service_example():
    scope = Scope()
    env = await MetricsLayer.build_scoped(Context(), scope)
    
    # Use the service
    def record_metric(name: str, value: float) -> Effect[MetricsCollector, None, None]:
        return service(MetricsCollector).map(lambda metrics: metrics.record(name, value))
    
    await record_metric("requests", 1)._run(env)
    await record_metric("requests", 1)._run(env)
    await record_metric("errors", 1)._run(env)
    
    await scope.close()

asyncio.run(provide_service_example())
```

## Service Composition Patterns

### Layered Architecture

```python
import asyncio
from effectpy import *

# Domain services
class UserRepository:
    async def find_by_id(self, user_id: int) -> dict | None:
        # Simulate database lookup
        users = {1: {"id": 1, "name": "Alice", "email": "alice@example.com"}}
        return users.get(user_id)

class EmailService:
    async def send_email(self, to: str, subject: str, body: str):
        print(f"📧 Email sent to {to}: {subject}")

class AuditLogger:
    def log_action(self, user_id: int, action: str):
        print(f"🔍 AUDIT: User {user_id} performed {action}")

# Business logic layer
class UserService:
    def get_user(self, user_id: int) -> Effect[UserRepository | AuditLogger, str, dict]:
        async def impl(ctx: Context):
            repo = ctx.get(UserRepository)
            audit = ctx.get(AuditLogger)
            
            audit.log_action(user_id, "get_user")
            
            user = await repo.find_by_id(user_id)
            if not user:
                return {"error": "User not found"}
            
            return user
        
        return Effect(impl)
    
    def send_welcome_email(self, user_id: int) -> Effect[UserRepository | EmailService | AuditLogger, str, None]:
        async def impl(ctx: Context):
            repo = ctx.get(UserRepository)
            email = ctx.get(EmailService)
            audit = ctx.get(AuditLogger)
            
            user = await repo.find_by_id(user_id)
            if not user:
                raise ValueError("User not found")
            
            await email.send_email(
                to=user["email"],
                subject="Welcome!",
                body=f"Welcome to our service, {user['name']}!"
            )
            
            audit.log_action(user_id, "welcome_email_sent")
        
        return Effect(impl)

# Service layers
UserRepositoryLayer = provide_service(UserRepository, UserRepository())
EmailServiceLayer = provide_service(EmailService, EmailService())
AuditLoggerLayer = provide_service(AuditLogger, AuditLogger())
UserServiceLayer = provide_service(UserService, UserService())

# Composed application layer
AppLayer = (UserRepositoryLayer | 
            EmailServiceLayer | 
            AuditLoggerLayer) + UserServiceLayer

async def layered_services_example():
    scope = Scope()
    env = await AppLayer.build_scoped(Context(), scope)
    
    user_service = env.get(UserService)
    
    # Use business logic
    user = await user_service.get_user(1)._run(env)
    print(f"User: {user}")
    
    await user_service.send_welcome_email(1)._run(env)
    
    await scope.close()

asyncio.run(layered_services_example())
```

## Configuration Management

### Environment-Based Configuration

```python
import asyncio
import os
from effectpy import *
from dataclasses import dataclass

@dataclass
class DatabaseConfig:
    host: str
    port: int
    database: str
    
    @classmethod
    def from_env(cls):
        return cls(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "myapp")
        )

@dataclass
class APIConfig:
    base_url: str
    timeout: int
    api_key: str
    
    @classmethod
    def from_env(cls):
        return cls(
            base_url=os.getenv("API_URL", "https://api.example.com"),
            timeout=int(os.getenv("API_TIMEOUT", "30")),
            api_key=os.getenv("API_KEY", "dev-key")
        )

# Configuration layers
DatabaseConfigLayer = provide_service(DatabaseConfig, DatabaseConfig.from_env())
APIConfigLayer = provide_service(APIConfig, APIConfig.from_env())

# Services that depend on configuration
class DatabaseConnection:
    def __init__(self, config: DatabaseConfig):
        self.config = config
        print(f"🔌 Connected to {config.host}:{config.port}/{config.database}")
    
    async def query(self, sql: str) -> list:
        await asyncio.sleep(0.1)  # Simulate query
        return [{"result": "data"}]

def DatabaseConnectionLayer() -> Layer:
    async def build(ctx: Context) -> Context:
        config = ctx.get(DatabaseConfig)
        connection = DatabaseConnection(config)
        return ctx.with_service(DatabaseConnection, connection)
    
    async def teardown(ctx: Context) -> None:
        # Connection cleanup would go here
        print("🔌 Database connection closed")
    
    return Layer(build=build, teardown=teardown)

# Complete application layer
ConfigLayer = DatabaseConfigLayer | APIConfigLayer
ServiceLayer = DatabaseConnectionLayer()
AppLayer = ConfigLayer + ServiceLayer

async def config_services_example():
    # Set some environment variables for demo
    os.environ["DB_HOST"] = "production-db.example.com"
    os.environ["DB_PORT"] = "5432"
    os.environ["API_URL"] = "https://prod-api.example.com"
    
    scope = Scope()
    env = await AppLayer.build_scoped(Context(), scope)
    
    # Use configured services
    def get_data() -> Effect[DatabaseConnection | APIConfig, str, dict]:
        async def impl(ctx: Context):
            db = ctx.get(DatabaseConnection)
            api_config = ctx.get(APIConfig)
            
            data = await db.query("SELECT * FROM users")
            return {
                "database_data": data,
                "api_endpoint": api_config.base_url,
                "configured_timeout": api_config.timeout
            }
        
        return Effect(impl)
    
    result = await get_data()._run(env)
    print(f"Application data: {result}")
    
    await scope.close()

asyncio.run(config_services_example())
```

## Testing with Services

### Mock Services for Testing

```python
import asyncio
from effectpy import *

# Production services
class EmailService:
    async def send_email(self, to: str, subject: str, body: str):
        print(f"📧 REAL EMAIL sent to {to}: {subject}")
        # Would actually send email

class PaymentProcessor:
    async def charge_card(self, amount: float, card_token: str) -> str:
        print(f"💳 REAL CHARGE: ${amount} on card {card_token}")
        # Would actually charge card
        return f"charge_id_{int(amount * 100)}"

# Test mocks
class MockEmailService:
    def __init__(self):
        self.sent_emails = []
    
    async def send_email(self, to: str, subject: str, body: str):
        self.sent_emails.append({"to": to, "subject": subject, "body": body})
        print(f"📧 MOCK EMAIL queued for {to}: {subject}")

class MockPaymentProcessor:
    def __init__(self):
        self.charges = []
    
    async def charge_card(self, amount: float, card_token: str) -> str:
        charge_id = f"mock_charge_{len(self.charges)}"
        self.charges.append({"amount": amount, "card_token": card_token, "charge_id": charge_id})
        print(f"💳 MOCK CHARGE: ${amount} (ID: {charge_id})")
        return charge_id

# Business logic (same for production and test)
def process_order(amount: float, email: str, card_token: str) -> Effect[EmailService | PaymentProcessor, str, dict]:
    async def impl(ctx: Context):
        email_service = ctx.get(EmailService)
        payment = ctx.get(PaymentProcessor)
        
        # Charge the card
        charge_id = await payment.charge_card(amount, card_token)
        
        # Send confirmation email
        await email_service.send_email(
            to=email,
            subject="Order Confirmation",
            body=f"Your order for ${amount} has been processed. Charge ID: {charge_id}"
        )
        
        return {
            "charge_id": charge_id,
            "amount": amount,
            "email_sent": True
        }
    
    return Effect(impl)

# Production layer
ProductionLayer = (provide_service(EmailService, EmailService()) |
                   provide_service(PaymentProcessor, PaymentProcessor()))

# Test layer
TestLayer = (provide_service(EmailService, MockEmailService()) |
             provide_service(PaymentProcessor, MockPaymentProcessor()))

async def test_services_example():
    # Test environment
    print("🧪 Running in TEST mode")
    scope = Scope()
    test_env = await TestLayer.build_scoped(Context(), scope)
    
    result = await process_order(29.99, "customer@example.com", "card_123")._run(test_env)
    print(f"Test result: {result}")
    
    # Verify mocks
    email_service = test_env.get(EmailService)
    payment_service = test_env.get(PaymentProcessor)
    
    assert len(email_service.sent_emails) == 1
    assert len(payment_service.charges) == 1
    assert payment_service.charges[0]["amount"] == 29.99
    
    print("✅ All tests passed!")
    
    await scope.close()
    
    # Production would use ProductionLayer instead
    print("\n🚀 Production would use real services:")
    prod_scope = Scope()
    prod_env = await ProductionLayer.build_scoped(Context(), prod_scope)
    
    # In production, this would send real emails and charge real cards
    print("(Skipping production run to avoid side effects)")
    
    await prod_scope.close()

asyncio.run(test_services_example())
```

## Advanced Service Patterns

### Service Factories

```python
import asyncio
from effectpy import *

class ConnectionPool:
    def __init__(self, max_connections: int):
        self.max_connections = max_connections
        self.active_connections = 0
        print(f"🏊 Created connection pool (max: {max_connections})")
    
    async def get_connection(self):
        if self.active_connections < self.max_connections:
            self.active_connections += 1
            return f"connection_{self.active_connections}"
        else:
            raise RuntimeError("Connection pool exhausted")
    
    async def release_connection(self, conn_id: str):
        self.active_connections -= 1
        print(f"🔄 Released {conn_id}")

# Service factory that creates services based on configuration
def create_connection_pool_layer(max_connections: int) -> Layer:
    return provide_service(ConnectionPool, ConnectionPool(max_connections))

# Different environments with different configurations
DevelopmentLayer = create_connection_pool_layer(max_connections=2)
ProductionLayer = create_connection_pool_layer(max_connections=20)

async def service_factory_example():
    # Development environment
    print("🛠️  Development environment")
    dev_scope = Scope()
    dev_env = await DevelopmentLayer.build_scoped(Context(), dev_scope)
    
    def use_connection_pool() -> Effect[ConnectionPool, str, list]:
        async def impl(ctx: Context):
            pool = ctx.get(ConnectionPool)
            
            connections = []
            for i in range(3):  # Try to get 3 connections
                try:
                    conn = await pool.get_connection()
                    connections.append(conn)
                    print(f"✅ Got connection: {conn}")
                except RuntimeError as e:
                    print(f"❌ {e}")
                    break
            
            # Release connections
            for conn in connections:
                await pool.release_connection(conn)
            
            return connections
        
        return Effect(impl)
    
    await use_connection_pool()._run(dev_env)
    await dev_scope.close()
    
    print("\n🚀 Production environment (higher limits)")
    prod_scope = Scope()
    prod_env = await ProductionLayer.build_scoped(Context(), prod_scope)
    await use_connection_pool()._run(prod_env)
    await prod_scope.close()

asyncio.run(service_factory_example())
```

### Service Composition

```python
import asyncio
from effectpy import *

# Low-level services
class HTTPClient:
    async def get(self, url: str) -> dict:
        await asyncio.sleep(0.1)
        return {"status": 200, "data": f"Response from {url}"}

class Cache:
    def __init__(self):
        self._cache = {}
    
    def get(self, key: str) -> str | None:
        return self._cache.get(key)
    
    def set(self, key: str, value: str, ttl: int = 3600):
        self._cache[key] = value  # Simplified - no TTL implementation

# Composite service that uses other services
class APIService:
    def fetch_with_cache(self, url: str) -> Effect[HTTPClient | Cache, str, dict]:
        async def impl(ctx: Context):
            http = ctx.get(HTTPClient)
            cache = ctx.get(Cache)
            
            # Check cache first
            cache_key = f"url:{url}"
            cached = cache.get(cache_key)
            
            if cached:
                print(f"💾 Cache hit for {url}")
                return {"cached": True, "data": cached}
            
            # Fetch from HTTP and cache
            print(f"🌐 Fetching from {url}")
            response = await http.get(url)
            cache.set(cache_key, str(response["data"]))
            
            return {"cached": False, "data": response["data"]}
        
        return Effect(impl)

# Service layers
HTTPClientLayer = provide_service(HTTPClient, HTTPClient())
CacheLayer = provide_service(Cache, Cache())
APIServiceLayer = provide_service(APIService, APIService())

CompositeServiceLayer = (HTTPClientLayer | CacheLayer) + APIServiceLayer

async def service_composition_example():
    scope = Scope()
    env = await CompositeServiceLayer.build_scoped(Context(), scope)
    
    api_service = env.get(APIService)
    
    # First call - cache miss
    result1 = await api_service.fetch_with_cache("https://api.example.com/data")._run(env)
    print(f"First call: {result1}")
    
    # Second call - cache hit
    result2 = await api_service.fetch_with_cache("https://api.example.com/data")._run(env)
    print(f"Second call: {result2}")
    
    await scope.close()

asyncio.run(service_composition_example())
```

## Best Practices

### 1. Use Clear Service Interfaces

```python
# ✅ Good: Clear, focused service interface
class UserRepository:
    async def find_by_id(self, user_id: int) -> User | None: ...
    async def save(self, user: User) -> User: ...
    async def delete(self, user_id: int) -> bool: ...

# ❌ Avoid: Kitchen sink services
class UserService:
    async def find_user(self, user_id: int): ...
    async def send_email(self, to: str, subject: str): ...
    async def log_action(self, action: str): ...
    async def validate_permissions(self, user: User): ...
```

### 2. Layer Composition Order Matters

```python
# ✅ Good: Dependencies first, then dependents
AppLayer = (ConfigLayer | LoggerLayer) + DatabaseLayer + ServiceLayer

# ❌ Wrong: Service needs Database but they're built in parallel  
WrongLayer = ServiceLayer | DatabaseLayer  # Race condition!
```

### 3. Use Type Hints for Service Requirements

```python
# ✅ Good: Clear service requirements
def fetch_user_data(user_id: int) -> Effect[Database | Logger | Cache, str, dict]:
    # Implementation knows exactly what services it needs
    ...

# ❌ Avoid: Generic requirements
def fetch_user_data(user_id: int) -> Effect[Any, Any, Any]:
    # Unclear what services are needed
    ...
```

### 4. Separate Service Definition from Usage

```python
# ✅ Good: Define services separately from business logic
class UserService:
    def get_user(self, user_id: int) -> Effect[UserRepository, str, User]:
        return service(UserRepository).flat_map(
            lambda repo: from_async(lambda: repo.find_by_id(user_id))
        )

# ❌ Avoid: Mixing service creation with business logic
def get_user(user_id: int, db_connection_string: str) -> Effect[Any, str, User]:
    # Creates tight coupling to implementation details
    ...
```

## What's Next?

- **→ [Layers & Scope](../concepts/layers_scope.md)** - Deep dive into resource management
- **→ [Effects](../concepts/effects.md)** - Understanding the Effect system
- **→ [Concurrency Guide](concurrency.md)** - Services in concurrent applications
- **→ [Context & Scope API Reference](../reference/context_scope.md)** - Complete service API

