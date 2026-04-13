"""conftest.py – agent-orchestrator tests"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parents[3] / "shared"))
sys.path.insert(0, str(pathlib.Path(__file__).parents[1]))
import pytest
pytest_plugins = ["pytest_asyncio"]
