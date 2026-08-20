"""conftest.py – root-level tests (security, integration)"""
import sys
import pathlib

ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "services" / "agent-orchestrator"))
