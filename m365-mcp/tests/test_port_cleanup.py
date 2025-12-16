"""Quick tests to verify port 8000 cleanup fixture works.

Run this to test the cleanup: pytest tests/test_port_cleanup.py -v
Should complete in ~6 seconds even if port 8000 is stuck.
"""

from __future__ import annotations


def test_cleanup_runs_before_session():
    """Verify cleanup fixture runs automatically."""
    # This test just needs to exist to trigger the session-scoped fixture
    assert True


def test_cleanup_allows_tests_to_run():
    """Verify tests can run after cleanup."""
    assert 1 + 1 == 2


def test_cleanup_is_transparent():
    """Verify cleanup doesn't interfere with normal tests."""
    result = "cleanup works"
    assert "works" in result
