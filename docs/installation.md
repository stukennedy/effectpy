# Installation

Prereqs: Python 3.10+

Options:

- Pip (latest):

  ```bash
  pip install effectpy
  ```

- Editable from source (dev):

  ```bash
  uv pip install -e .
  ```

- Optional extras:

  - `anyio`: AnyIO runtime example
  - `exporters`: aiohttp-based OTLP exporters
  - `docs`: MkDocs + Material + mkdocstrings

  ```bash
  uv pip install -e .[docs]
  ```

