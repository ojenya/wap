"""Deterministic multi-agent workflow package.

The core lifecycle is a hardcoded, versioned state graph (intake -> audit ->
analysis -> spec -> develop -> static checks -> sandbox -> review -> report ->
learn). Individual stages are pluggable agents implementing the ``Stage``
protocol; MVP ships deterministic stub agents so the graph runs without any
external LLM/tooling credentials.
"""
