"""
core — Safety infrastructure for LNVE.

Provides rate limiting, proxy rotation, and safe HTTP requests
with automatic retries and exponential backoff.

Usage:
    from core import TokenBucket, ProxyManager, safe_api_call
"""

from .rate_limit import TokenBucket
from .proxy_manager import ProxyManager
from .safe_request import safe_api_call, batch_delay

__all__ = ["TokenBucket", "ProxyManager", "safe_api_call", "batch_delay"]
