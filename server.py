"""Unsiloed AI internal-ops MCP server (mock data).

Run (stdio, for Claude Desktop / Cursor / VS Code):   python server.py
Run (HTTP, for a shared team server):                 python server.py --transport http

All real logic lives in core.py; this file only exposes it over MCP.
Tool descriptions are written plainly on purpose, so smaller models also pick
the right tool.

Works with every common install:
  * mcp 2.x   (official SDK v2)    -> mcp.server.mcpserver.MCPServer
  * mcp 1.x   (official SDK v1)    -> mcp.server.fastmcp.FastMCP
  * fastmcp   (standalone package) -> fastmcp.FastMCP
"""
import argparse
import os

try:                                            # official SDK v2 (FastMCP was renamed MCPServer)
    from mcp.server.mcpserver import MCPServer as _Server
    FLAVOR = "sdk-v2"
except ImportError:
    try:                                        # official SDK v1
        from mcp.server.fastmcp import FastMCP as _Server
        FLAVOR = "sdk-v1"
    except ImportError:
        try:                                    # standalone fastmcp package
            from fastmcp import FastMCP as _Server
            FLAVOR = "standalone-fastmcp"
        except ImportError:
            raise SystemExit(
                "No MCP library found for THIS Python. Run:\n"
                "    python -m pip install -U \"mcp[cli]\"\n"
                "(use 'python -m pip' so it installs into the same Python that runs this file; "
                "Python 3.10+ is required)."
            )

import core

HOST = os.environ.get("MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("MCP_PORT", "8000"))

# Only the name is passed to the constructor: host/port moved to run() in newer versions.
mcp = _Server("unsiloed-ops")


@mcp.tool()
def get_parse_job(job_id: str) -> str:
    """Get the status of ONE document parsing job.

    Use this when someone asks "is job X done?", "why did job X fail?" or "is it stuck?".
    Warns if the job has been running much longer than expected.

    Args:
        job_id: Job ID such as JOB-1004. Valid IDs are JOB-1001 to JOB-1030.
    """
    return core.get_parse_job(job_id)


@mcp.tool()
def check_batch_quality(batch_id: str, threshold: float = 0.80) -> str:
    """Scan a whole batch and list the pages that look risky BEFORE it is delivered.

    Flags pages with low parser confidence, a known issue type, or missing required fields.
    Use this first when reviewing a batch. It does NOT find confident mistakes; for those
    use compare_source_vs_parsed.

    Args:
        batch_id: Batch ID such as BATCH-03. Valid IDs are BATCH-01 to BATCH-05.
        threshold: Confidence below this number is flagged. Between 0 and 1. Default 0.80.
    """
    return core.check_batch_quality(batch_id, threshold)


@mcp.tool()
def compare_source_vs_parsed(job_id: str, page: int) -> str:
    """Compare ONE page of the customer's original document with what our parser produced.

    Lists exact differences: changed numbers, missing table rows, merged cells, dropped
    charts or footnotes, and text in the wrong order. Use this to confirm what is wrong on a
    page, or to spot check a page that was not flagged.

    Args:
        job_id: Job ID such as JOB-1004.
        page: Page number, starting at 1.
    """
    return core.compare_source_vs_parsed(job_id, page)


@mcp.tool()
def run_regression_check(old_version: str = "v1.4", new_version: str = "v2.0") -> str:
    """Check whether a new parser version made saved sample documents worse than the old one.

    Use this before or after rolling out a parser update. Lists documents that got worse,
    documents that got better, and the kind of new problem introduced.

    Args:
        old_version: Older parser version, for example v1.4.
        new_version: Newer parser version, for example v2.0.
    """
    return core.run_regression_check(old_version, new_version)


@mcp.tool()
def search_failure_playbook(question: str) -> str:
    """Search past failure reports for the cause and fix of a parsing problem.

    Returns only the 3 most relevant short passages, not whole documents. Use plain words
    that describe the problem, for example "merged table cells", "rotated scan",
    "dropped digit", "stuck job timeout".

    Args:
        question: A short description of the problem you are trying to solve.
    """
    return core.search_failure_playbook(question)


@mcp.resource("schema://document-types")
def document_types() -> str:
    """The document types we parse, with required output fields and expected speed."""
    return core.document_types()


@mcp.prompt()
def triage_flagged_batch(batch_id: str) -> str:
    """Step-by-step triage of a batch before delivery, ending in a summary for a human."""
    return core.triage_prompt(batch_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    args = parser.parse_args()
    if args.transport == "stdio":
        mcp.run(transport="stdio")
    elif FLAVOR == "sdk-v2":
        mcp.run(transport="streamable-http", host=HOST, port=PORT)
    elif FLAVOR == "sdk-v1":
        mcp.settings.host, mcp.settings.port = HOST, PORT
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="http", host=HOST, port=PORT)