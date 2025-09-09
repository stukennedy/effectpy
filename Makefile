.PHONY: test examples-list example-basic example-layers example-provide example-fibers example-pipelines example-anyio example-exporters install-anyio install-aiohttp

test:
	uv run python -m unittest discover -s tests -p 'test_*.py' -v

examples-list:
	@echo "Available example targets:"
	@echo "  make example-basic       # basic effects + instrumentation"
	@echo "  make example-layers      # layers + resource safety"
	@echo "  make example-provide     # provide() scoped layer"
	@echo "  make example-fibers      # runtime + fibers concurrency"
	@echo "  make example-pipelines   # pipelines + channels"
	@echo "  make example-anyio       # AnyIO runtime (optional anyio)"
	@echo "  make example-exporters   # exporters (optional aiohttp)"

example-basic:
	uv run python -m examples.basic_effects

example-layers:
	uv run python -m examples.layers_resource_safety

example-provide:
	uv run python -m examples.provide_layer_example

example-fibers:
	uv run python -m examples.fibers_concurrency

example-pipelines:
	uv run python -m examples.pipelines_parallel

example-anyio:
	uv run python -m examples.anyio_runtime_example

example-exporters:
	uv run python -m examples.exporters_demo

install-anyio:
	uv pip install anyio

install-aiohttp:
	uv pip install aiohttp
docs-serve:
	uv run mkdocs serve -a localhost:8000

docs-build:
	uv run mkdocs build --clean

docs-deploy:
	uv run mkdocs gh-deploy --force
