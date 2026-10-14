"""Comprehensive unit tests for SafeFetcher and SSRF protection.

Covers:
1. IP validation: IPv4, IPv6, IPv4-mapped IPv6, CGNAT, 6to4, and documentation ranges.
2. URL syntax: scheme, standard ports, and embedded credentials rejection.
3. Public success with controlled mock transport.
4. Private IPv4, IPv6, and mapped-address rejection before connection.
5. Public-to-private redirects (SSRF blocked on redirect hop).
6. DNS changing between validation and connection (DNS rebinding defense).
7. Redirect limits (abort after 3 hops).
8. Unsupported content-type rejection before reading body.
9. Oversize stream rejection (exceeding 1 MB limit).
10. Overall fetch deadline enforcement.
11. Direct exercise of SafeNetworkBackend and connection-enforcement logic.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
import pytest
import httpx

from app.retrieval.safe_fetcher import (
    DEFAULT_MAX_REDIRECTS,
    DEFAULT_MAX_RESPONSE_BYTES,
    SafeAsyncHTTPTransport,
    SafeFetcher,
    SafeFetchError,
    SafeNetworkBackend,
    SSRFBlockedError,
    is_public_ip,
    validate_url_syntax,
)
from app.search.models import SourceFetchState


# ---------------------------------------------------------------------------
# 1. IP Validation Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "ip_str, expected_ok, expected_snippet",
    [
        # Loopback
        ("127.0.0.1", False, "Loopback"),
        ("127.0.1.1", False, "Loopback"),
        ("::1", False, "Loopback"),
        # Private RFC 1918 & ULA
        ("10.0.0.1", False, "Private"),
        ("172.16.0.1", False, "Private"),
        ("172.31.255.255", False, "Private"),
        ("192.168.1.1", False, "Private"),
        ("fc00::1", False, "Private"),
        ("fd12:3456::1", False, "Private"),
        # Link-local & cloud metadata
        ("169.254.169.254", False, "Link-local"),
        ("fe80::1", False, "Link-local"),
        # Carrier-grade NAT
        ("100.64.0.1", False, "100.64.0.0/10"),
        ("100.127.255.255", False, "100.64.0.0/10"),
        # IPv4-mapped IPv6 bypasses
        ("::ffff:127.0.0.1", False, "Loopback"),
        ("::ffff:10.0.0.1", False, "Private"),
        ("::ffff:169.254.169.254", False, "Link-local"),
        ("::ffff:7f00:1", False, "Loopback"),
        ("::127.0.0.1", False, "Loopback"),
        # 6to4 embedded loopback
        ("2002:7f00:0001::", False, "6to4 embedded private IP"),
        # Documentation & Unspecified
        ("0.0.0.0", False, "Unspecified"),
        ("192.0.2.1", False, "Private"),
        ("198.51.100.1", False, "Private"),
        ("203.0.113.1", False, "Private"),
        ("2001:db8::1", False, "Private"),
        # Valid Public IPs
        ("93.184.216.34", True, "Public"),
        ("8.8.8.8", True, "Public"),
        ("1.1.1.1", True, "Public"),
        ("2606:2800:220:1:248:1893:25c8:1946", True, "Public"),
    ],
)
def test_is_public_ip_coverage(ip_str: str, expected_ok: bool, expected_snippet: str):
    ok, reason = is_public_ip(ip_str)
    assert ok is expected_ok, f"Failed for {ip_str}: got {ok} ({reason}), expected {expected_ok}"
    assert expected_snippet.lower() in reason.lower()


# ---------------------------------------------------------------------------
# 2. URL Syntax & Port Validation Tests
# ---------------------------------------------------------------------------

def test_url_syntax_permits_standard_http_https():
    p1 = validate_url_syntax("http://example.com/article")
    assert p1.scheme == "http"
    assert p1.port is None

    p2 = validate_url_syntax("https://example.com:443/article")
    assert p2.scheme == "https"
    assert p2.port == 443


@pytest.mark.parametrize(
    "url, error_match",
    [
        ("file:///etc/passwd", "Unsupported scheme"),
        ("ftp://example.com/file", "Unsupported scheme"),
        ("gopher://example.com/", "Unsupported scheme"),
        ("javascript:alert(1)", "Unsupported scheme"),
        ("http://user:pass@example.com/page", "embedded user credentials"),
        ("https://admin@example.com/", "embedded user credentials"),
        ("http://example.com:8080/page", "Non-standard HTTP port"),
        ("https://example.com:8443/page", "Non-standard HTTPS port"),
        ("http://example.com:22/page", "Non-standard HTTP port"),
        ("https://example.com:bad/path", "Invalid port"),
        ("https://example.com:99999/path", "Invalid port"),
        ("http:///empty-host", "valid hostname"),
    ],
)
def test_url_syntax_rejects_unsafe_inputs(url: str, error_match: str):
    with pytest.raises(SafeFetchError) as exc:
        validate_url_syntax(url)
    assert error_match.lower() in str(exc.value).lower()


# ---------------------------------------------------------------------------
# 3. Public Success with Controlled Mock Transport
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_safe_fetcher_public_success():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("User-Agent") is not None
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            text="<html><body><h1>Los Angeles Homeless Count</h1><p>Facts here.</p></body></html>",
        )

    transport = httpx.MockTransport(mock_handler)
    fetcher = SafeFetcher(
        dns_resolver=lambda host: ["93.184.216.34"],
        custom_transport=transport,
    )

    result = await fetcher.fetch("https://news.example.org/article-123")
    assert result.status == SourceFetchState.RETRIEVED
    assert result.http_status_code == 200
    assert result.extracted_text is not None
    assert "Los Angeles Homeless Count" in result.extracted_text
    assert result.redirect_count == 0
    assert result.resolved_ip == "93.184.216.34"
    assert result.error_message is None


# ---------------------------------------------------------------------------
# 4. Private IPv4, IPv6, and Mapped Address Rejection
# ---------------------------------------------------------------------------

@pytest.mark.anyio
@pytest.mark.parametrize(
    "resolved_ip",
    [
        "127.0.0.1",
        "10.0.0.5",
        "192.168.0.1",
        "169.254.169.254",
        "::1",
        "fe80::1",
        "fc00::1",
        "::ffff:127.0.0.1",
        "::ffff:169.254.169.254",
        "100.64.0.1",
    ],
)
async def test_safe_fetcher_rejects_non_public_ips_before_connecting(resolved_ip: str):
    fetch_attempted = False

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal fetch_attempted
        fetch_attempted = True
        return httpx.Response(200, text="should not reach here")

    transport = httpx.MockTransport(mock_handler)
    fetcher = SafeFetcher(
        dns_resolver=lambda host: [resolved_ip],
        custom_transport=transport,
    )

    result = await fetcher.fetch("https://attacker.example.org/secret")
    assert result.status == SourceFetchState.SSRF_BLOCKED
    assert "SSRF_BLOCKED" in (result.error_message or "")
    assert not fetch_attempted, "Connection was attempted despite non-public IP!"
    assert result.extracted_text is None


# ---------------------------------------------------------------------------
# 5. Public-to-Private Redirect Rejection
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_safe_fetcher_blocks_public_to_private_redirect():
    # Hop 1 is public news site that returns 302 to AWS metadata service
    def mock_handler(request: httpx.Request) -> httpx.Response:
        if "news.example.org" in str(request.url):
            return httpx.Response(
                302,
                headers={"Location": "http://169.254.169.254/latest/meta-data"},
            )
        return httpx.Response(200, text="should not be reached")

    transport = httpx.MockTransport(mock_handler)

    def dynamic_dns(host: str) -> list[str]:
        if "news.example.org" in host:
            return ["93.184.216.34"]  # Public IP for hop 1
        return [host]  # Hop 2 is IP literal

    fetcher = SafeFetcher(
        dns_resolver=dynamic_dns,
        custom_transport=transport,
    )

    result = await fetcher.fetch("http://news.example.org/tracker")
    assert result.status == SourceFetchState.SSRF_BLOCKED
    assert "SSRF_BLOCKED" in (result.error_message or "")
    assert "169.254.169.254" in (result.error_message or "")
    assert result.redirect_count == 1
    assert result.extracted_text is None


# ---------------------------------------------------------------------------
# 6. DNS Rebinding Defense (Changing Between Validation & Connection)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_safe_network_backend_blocks_dns_rebinding_at_connect_time():
    """Simulate DNS rebinding: host returns public during precheck, but switches to 127.0.0.1 at connect time."""
    resolution_count = 0

    def rebinding_dns(host: str) -> list[str]:
        nonlocal resolution_count
        resolution_count += 1
        if resolution_count == 1:
            return ["93.184.216.34"]  # Public on pre-check
        return ["127.0.0.1"]          # Switches to private at connect_tcp time!

    backend = SafeNetworkBackend(dns_resolver=rebinding_dns)

    # Precheck resolves public
    precheck_ips = rebinding_dns("rebinding.example.org")
    assert is_public_ip(precheck_ips[0])[0] is True

    # Now connect_tcp runs: it must catch the rebinding switch and raise SSRFBlockedError
    with pytest.raises(SSRFBlockedError) as exc:
        await backend.connect_tcp("rebinding.example.org", 80)
    assert "127.0.0.1" in str(exc.value)


# ---------------------------------------------------------------------------
# 7. Redirect Limit Enforcement (Max 3 Hops)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_safe_fetcher_enforces_redirect_limit():
    hop = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal hop
        hop += 1
        return httpx.Response(302, headers={"Location": f"https://example.org/hop{hop}"})

    transport = httpx.MockTransport(mock_handler)
    fetcher = SafeFetcher(
        max_redirects=3,
        dns_resolver=lambda host: ["93.184.216.34"],
        custom_transport=transport,
    )

    result = await fetcher.fetch("https://example.org/hop0")
    assert result.status == SourceFetchState.INACCESSIBLE
    assert "REDIRECT_LIMIT" in (result.error_message or "")
    assert result.redirect_count == 4  # Stopped after exceeding 3
    assert result.extracted_text is None


# ---------------------------------------------------------------------------
# 8. MIME Policy Enforcement
# ---------------------------------------------------------------------------

@pytest.mark.anyio
@pytest.mark.parametrize(
    "content_type",
    [
        "application/pdf",
        "image/png",
        "application/octet-stream",
        "application/zip",
        "video/mp4",
    ],
)
async def test_safe_fetcher_rejects_unsupported_mime_types(content_type: str):
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": content_type},
            content=b"%PDF-1.4 binary data...",
        )

    transport = httpx.MockTransport(mock_handler)
    fetcher = SafeFetcher(
        dns_resolver=lambda host: ["93.184.216.34"],
        custom_transport=transport,
    )

    result = await fetcher.fetch("https://example.org/document.pdf")
    assert result.status == SourceFetchState.INACCESSIBLE
    assert "UNSUPPORTED_MIME" in (result.error_message or "")
    assert content_type in (result.error_message or "")
    assert result.extracted_text is None


# ---------------------------------------------------------------------------
# 9. Oversize Stream Ceiling Enforcement (1 MB Cap)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_safe_fetcher_rejects_content_length_oversize():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "Content-Type": "text/html",
                "Content-Length": str(2_000_000),  # 2 MB announced
            },
            content=b"too large",
        )

    transport = httpx.MockTransport(mock_handler)
    fetcher = SafeFetcher(
        max_response_bytes=1_048_576,
        dns_resolver=lambda host: ["93.184.216.34"],
        custom_transport=transport,
    )

    result = await fetcher.fetch("https://example.org/large.html")
    assert result.status == SourceFetchState.INACCESSIBLE
    assert "OVERSIZED" in (result.error_message or "")
    assert result.extracted_text is None


@pytest.mark.anyio
async def test_safe_fetcher_aborts_stream_exceeding_1mb():
    chunk = b"A" * 65536  # 64 KB

    async def streaming_generator():
        for _ in range(20):  # 20 * 64 KB = 1.28 MB
            yield chunk

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html"},
            content=streaming_generator(),
        )

    transport = httpx.MockTransport(mock_handler)
    fetcher = SafeFetcher(
        max_response_bytes=1_048_576,
        dns_resolver=lambda host: ["93.184.216.34"],
        custom_transport=transport,
    )

    result = await fetcher.fetch("https://example.org/stream-large")
    assert result.status == SourceFetchState.INACCESSIBLE
    assert "OVERSIZED" in (result.error_message or "")
    assert result.extracted_text is None


# ---------------------------------------------------------------------------
# 10. Overall Fetch Deadline Enforcement
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_safe_fetcher_enforces_overall_deadline():
    async def slow_handler(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.5)
        return httpx.Response(200, headers={"Content-Type": "text/html"}, text="<p>slow</p>")

    transport = httpx.MockTransport(slow_handler)
    fetcher = SafeFetcher(
        overall_timeout_seconds=0.1,  # Strict 100ms deadline
        dns_resolver=lambda host: ["93.184.216.34"],
        custom_transport=transport,
    )

    t0 = time.monotonic()
    result = await fetcher.fetch("https://example.org/slow")
    elapsed = time.monotonic() - t0

    assert result.status == SourceFetchState.INACCESSIBLE
    assert "TIMEOUT" in (result.error_message or "")
    assert result.extracted_text is None
    # Must abort near the 100ms deadline, well before the 500ms sleep completes
    assert elapsed < 0.35, f"Elapsed time {elapsed:.3f}s exceeded expected deadline tolerance"


@pytest.mark.anyio
async def test_safe_fetcher_enforces_deadline_on_slow_dns():
    """Verify that slow DNS resolution is cancelled within overall_timeout_seconds."""
    async def slow_dns(hostname: str) -> list[str]:
        await asyncio.sleep(0.2)
        return ["93.184.216.34"]

    fetcher = SafeFetcher(
        overall_timeout_seconds=0.05,  # 50ms deadline vs 200ms DNS
        dns_resolver=slow_dns,
    )

    t0 = time.monotonic()
    result = await fetcher.fetch("https://example.org/page")
    elapsed = time.monotonic() - t0

    assert result.status == SourceFetchState.INACCESSIBLE
    assert "TIMEOUT" in (result.error_message or "")
    assert elapsed < 0.15, f"DNS cancellation took too long: {elapsed:.3f}s"


# ---------------------------------------------------------------------------
# 11. Exercise Actual Connection-Enforcement Backend
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_safe_network_backend_binds_to_validated_ip():
    """Verify that SafeNetworkBackend resolves and binds target_ip to connect_tcp."""
    class DummyStream:
        def get_extra_info(self, name: str):
            return None

    class MockUnderlyingBackend:
        def __init__(self):
            self.connected_host = None
            self.connected_port = None

        async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
            self.connected_host = host
            self.connected_port = port
            return DummyStream()

    mock_underlying = MockUnderlyingBackend()

    backend = SafeNetworkBackend(
        dns_resolver=lambda h: ["93.184.216.34"],
        underlying_backend=mock_underlying,
    )

    await backend.connect_tcp("news.example.org", 443)
    assert mock_underlying.connected_host == "93.184.216.34"
    assert mock_underlying.connected_port == 443
    assert backend.last_connected_ip == "93.184.216.34"
