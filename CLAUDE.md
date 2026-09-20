# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup (a .venv may already exist; `uv venv` errors rather than reusing it)
uv venv
source .venv/bin/activate
uv pip install -e .

# Run the MCP server (stdio transport)
uv run main.py

# Tests
uv run pytest
uv run pytest tests/test_document.py                                    # one file
uv run pytest "tests/test_document.py::TestBinaryDocumentToMarkdown::test_binary_document_to_markdown_with_pdf"
```

`uv run` syncs `.venv` to `uv.lock` first, so it will roll back versions that a looser `uv pip install` had resolved higher.

## Architecture

An MCP server exposing document-processing utilities. Two layers, deliberately separated:

- `tools/*.py` — plain Python functions with no MCP dependency. Directly unit-testable; import them in tests without spinning up a server.
- `main.py` — the only MCP-aware module. Constructs `FastMCP("docs")` and registers functions with `mcp.tool()(fn)`.

Adding a tool means writing the function in `tools/` **and** registering it in `main.py`. These are separate steps, and a function in `tools/` is dead code until registered. `binary_document_to_markdown` in `tools/document.py` is currently unregistered.

## Defining MCP tools

Tools are plain functions registered with the server by call, not by decorator, which is what keeps `tools/` importable without MCP:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("docs")
mcp.tool()(my_function)
```

`FastMCP` derives the entire tool schema by introspecting the function, so the signature and docstring **are** the wire contract that the calling model sees — they are not merely developer documentation. Type hints become the JSON schema types; the return annotation defines the result type.

Describe every parameter with `Field` from pydantic:

```python
from pydantic import Field

def my_tool(
    param1: str = Field(description="Detailed description of this parameter"),
    param2: int = Field(description="Explain what this parameter does")
) -> ReturnType:
    """Comprehensive docstring here"""
```

Per the README, each tool description should:

- Begin with a one-line summary
- Provide a detailed explanation of functionality
- Explain when to use (and when not to use) the tool
- Include usage examples with expected input/output

`tools/math.py` is the reference implementation of that docstring shape — summary line, prose explanation, a `When to use:` bullet list, then doctest-style `Examples:`. Follow it when adding tools; note its examples show `add(2, 3)` returning `5.0` rather than `5`, i.e. they reflect the annotated return type instead of what Python would literally print.

Because `Field(...)` occupies the default-value slot, these functions have no real Python defaults: omitting an argument binds a `FieldInfo` object instead of a number or string. Only the MCP layer fills values in from the schema, so tests and any other direct caller must pass every argument explicitly.

## Tests

`tests/test_document.py` groups cases in a plain class (no unittest base) and resolves binary inputs from `tests/fixtures/` relative to `__file__`, so tests pass regardless of the invocation directory. New format-conversion tests should add a fixture there rather than synthesizing document bytes inline.

## Repo-specific gotchas

- **No `__init__.py` files.** They were removed in `13fbe4e` and `*/__init__.py` is in `.gitignore` — do not add them back. Imports like `from tools.document import ...` work because `[tool.pytest.ini_options] pythonpath = ["."]` in `pyproject.toml` puts the project root on `sys.path`; without it pytest only sees `tests/`.
- The editable install exposes only `main` as a top-level module (setuptools finds no packages without `__init__.py`, and `uv.lock` records the project itself as `source = { virtual = "." }`). `tools` resolves via the current working directory, so commands must run from the project root.
- `mcp[cli]` is pinned exactly (`==1.8.0`) while the other dependencies use `>=`; `FastMCP` lives at `mcp.server.fastmcp` in that version.
