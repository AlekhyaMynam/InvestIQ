"""Pytest configuration — ensures test isolation from developer's local .env.

This file is loaded by pytest before any test module import or discovery,
so environment variables set here are available during module-level code
execution of all test and source modules.
"""
from __future__ import annotations

import os

# Signal to src/investiq/config.py that we are running under pytest.
# This prevents load_dotenv() from loading the developer's local .env
# file during module imports, ensuring tests are deterministic and
# independent of the developer's local configuration.
os.environ["INVESTIQ_TESTING"] = "1"

# Override LLM_PROVIDER to mock during all test sessions.
# This ensures test isolation from the developer's environment variables
# (whether set via .env, User/Machine environment variables, or shell).
# Tests that explicitly need to test Gemini configuration must use
# monkeypatch.setenv() to temporarily override this default.
os.environ["LLM_PROVIDER"] = "mock"
os.environ["INVESTIQ_ALLOW_REAL_LLM"] = "false"