# Installation

## Requirements

- **Python 3.10+**
- Compatible with `asyncio` and `anyio` (Trio support)

## Quick Install

=== "pip"

    ```bash
    pip install effectpy
    ```

=== "uv (recommended)"

    ```bash
    uv add effectpy
    ```

=== "conda"

    ```bash
    # Coming soon to conda-forge
    pip install effectpy
    ```

## Optional Dependencies

effectpy has several optional dependencies for enhanced functionality:

### AnyIO Runtime

For Trio/AnyIO backend support:

=== "pip"
    ```bash
    pip install effectpy[anyio]
    ```

=== "uv"
    ```bash
    uv add "effectpy[anyio]"
    ```

### Exporters

For OpenTelemetry HTTP exporters (requires `aiohttp`):

=== "pip"
    ```bash
    pip install effectpy[exporters]
    ```

=== "uv"
    ```bash  
    uv add "effectpy[exporters]"
    ```

### All Optional Dependencies

=== "pip"
    ```bash
    pip install effectpy[anyio,exporters]
    ```

=== "uv"
    ```bash
    uv add "effectpy[anyio,exporters]"
    ```

## Development Installation

For contributing or running examples:

=== "uv (recommended)"

    ```bash
    git clone https://github.com/stukennedy/effectpy.git
    cd effectpy
    uv sync
    ```

=== "pip"

    ```bash
    git clone https://github.com/stukennedy/effectpy.git
    cd effectpy
    pip install -e ".[anyio,exporters,docs]"
    ```

## Verify Installation

Create a simple test file to verify your installation:

```python title="test_effectpy.py"
import asyncio
from effectpy import *

async def main():
    # Simple effect composition
    result = await succeed(42).map(lambda x: x * 2)._run(Context())
    print(f"Effect result: {result}")  # Should print: Effect result: 84

    # Test resource management
    scope = Scope()
    env = await LoggerLayer.build_scoped(Context(), scope)
    
    instrumented = instrument("test", succeed("Hello effectpy!"))
    message = await instrumented._run(env)
    print(f"Instrumented: {message}")
    
    await scope.close()

if __name__ == "__main__":
    asyncio.run(main())
```

Run it:

```bash
python test_effectpy.py
```

Expected output:
```
Effect result: 84
Instrumented: Hello effectpy!
```

## What's Next?

- :octicons-arrow-right-24: [Quick Start Tutorial](quickstart.md)
- :octicons-arrow-right-24: [Core Concepts](concepts/effects.md)
- :octicons-arrow-right-24: [Example Applications](quickstart.md#examples)

## Troubleshooting

### Python Version Issues

Make sure you're using Python 3.10+:

```bash
python --version  # Should be 3.10.0 or higher
```

### Import Errors

If you see import errors, try:

1. **Reinstall effectpy**: `pip uninstall effectpy && pip install effectpy`
2. **Check virtual environment**: Make sure you're in the correct virtual environment
3. **Clear Python cache**: `python -Bc "import sys; print(sys.path)"`

### Optional Dependencies Not Found

If optional features don't work:

```bash
# Check what's installed
pip show effectpy

# Install missing extras
pip install effectpy[anyio,exporters]
```

