"""Integration test conftest – sets up sys.path for the full monorepo."""
import sys, pathlib

ROOT = pathlib.Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "services" / "agent-orchestrator"))
