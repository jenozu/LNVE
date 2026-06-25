"""Tests for core safety modules."""

import time
import pytest

from core.rate_limit import TokenBucket
from core.proxy_manager import ProxyManager


class TestTokenBucket:
    def test_allows_burst(self):
        b = TokenBucket(rate_per_sec=10, capacity=5)
        start = time.monotonic()
        for _ in range(5):
            b.wait()
        assert time.monotonic() - start < 1.0, "Burst should be near-instant"

    def test_rate_limiting(self):
        b = TokenBucket(rate_per_sec=4, capacity=1)
        start = time.monotonic()
        for _ in range(4):
            b.wait()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.5, f"4 calls at 4/s should take ≥ 0.5s, got {elapsed:.2f}s"

    def test_available_tokens(self):
        b = TokenBucket(rate_per_sec=2, capacity=2)
        assert b.available <= 2.0


class TestProxyManager:
    def test_no_proxies(self):
        mgr = ProxyManager([])
        assert mgr.get_proxy() is None

    def test_returns_proxy(self):
        mgr = ProxyManager(["http://proxy1:8080"])
        p = mgr.get_proxy()
        assert p == "http://proxy1:8080"

    def test_banning(self):
        mgr = ProxyManager(["http://proxy1:8080"], fail_threshold=2, cooldown=300)
        mgr.report_failure("http://proxy1:8080")
        mgr.report_failure("http://proxy1:8080")
        assert mgr.get_proxy() is None

    def test_success_resets_fails(self):
        mgr = ProxyManager(["http://proxy1:8080"], fail_threshold=3)
        mgr.report_failure("http://proxy1:8080")
        mgr.report_success("http://proxy1:8080")
        # Should not be banned after one success
        assert mgr.get_proxy() == "http://proxy1:8080"
