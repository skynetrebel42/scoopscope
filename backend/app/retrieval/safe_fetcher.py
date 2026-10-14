"""Safe URL fetcher with comprehensive SSRF protection and streaming constraints.

Per AGENTS.md, docs/evidence-search-design.md, and Milestone 2B requirements:
- HTTP/HTTPS only on standard ports (80 / 443).
- Rejects embedded URL credentials.
- Validates IPv4 and IPv6 destinations, including IPv4-mapped IPv6 and CGNAT.
- Binds TCP connection to the validated IP while preserving SNI and TLS verification for origin hostname.
- Rejects environment proxies (trust_env=False).
- Manual redirect loop with max 3 hops; re-checks SSRF on each hop.
- Enforces MIME policy (text/html, text/plain, application/xhtml+xml).
- Enforces 1 MB streamed/decompressed size limit.
- Enforces monotonic overall deadline across all hops and phases.
- Produces structured RetrievedSource with explicit failure reasons.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
import inspect
import ipaddress
import logging
import re
import socket
import time
from typing import Any
import urllib.parse
import uuid

import httpcore
from httpcore._backends.auto import AutoBackend
import httpx

from app.search.models import RetrievedSource, SourceFetchState

logger = logging.getLogger(__name__)

# Constants
DEFAULT_MAX_REDIRECTS = 3
DEFAULT_MAX_RESPONSE_BYTES = 1_048_576  # 1 MB (1024 * 1024)
DEFAULT_OVERALL_TIMEOUT_SECONDS = 30.0
DEFAULT_ALLOWED_CONTENT_TYPES = (
    "text/html",
    "text/plain",
    "application/xhtml+xml",
)
USER_AGENT = "ScoopScope-EvidenceFetcher/0.1 (+https://github.com/scoopscope/scoopscope)"

# Network blocklist for private, loopback, link-local, carrier-grade NAT, and reserved addresses
BLOCKED_NETWORKS: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = (
    # IPv4
    ipaddress.ip_network("0.0.0.0/8"),          # Current network
    ipaddress.ip_network("10.0.0.0/8"),         # Private (RFC 1918)
    ipaddress.ip_network("100.64.0.0/10"),      # Carrier-Grade NAT (RFC 6598)
    ipaddress.ip_network("127.0.0.0/8"),        # Loopback (RFC 1122)
    ipaddress.ip_network("169.254.0.0/16"),     # Link-local (RFC 3927)
    ipaddress.ip_network("172.16.0.0/12"),      # Private (RFC 1918)
    ipaddress.ip_network("192.0.0.0/24"),       # IETF Protocol Assignments
    ipaddress.ip_network("192.0.2.0/24"),       # Documentation (TEST-NET-1)
    ipaddress.ip_network("192.88.99.0/24"),     # 6to4 Relay Anycast (RFC 7526)
    ipaddress.ip_network("192.168.0.0/16"),     # Private (RFC 1918)
    ipaddress.ip_network("198.18.0.0/15"),      # Benchmarking
    ipaddress.ip_network("198.51.100.0/24"),    # Documentation (TEST-NET-2)
    ipaddress.ip_network("203.0.113.0/24"),     # Documentation (TEST-NET-3)
    ipaddress.ip_network("224.0.0.0/4"),        # Multicast (RFC 5771)
    ipaddress.ip_network("240.0.0.0/4"),        # Reserved (RFC 1112)
    ipaddress.ip_network("255.255.255.255/32"), # Broadcast
    # IPv6
    ipaddress.ip_network("::1/128"),            # Loopback
    ipaddress.ip_network("::/128"),             # Unspecified
    ipaddress.ip_network("100::/64"),           # Discard prefix
    ipaddress.ip_network("2001:db8::/32"),      # Documentation
    ipaddress.ip_network("fc00::/7"),           # Unique Local Address (ULA)
    ipaddress.ip_network("fe80::/10"),          # Link-local unicast
    ipaddress.ip_network("ff00::/8"),           # Multicast
)


class SafeFetchError(Exception):
    """Base exception for safe fetcher validation or execution failures."""


class SSRFBlockedError(SafeFetchError):
    """Raised when an address or target violates SSRF boundaries."""


def is_public_ip(ip_str: str) -> tuple[bool, str]:
    """Validate whether an IP address is a safe, publicly routable unicast address.
    
    Handles IPv4, IPv6, IPv4-mapped IPv6, and 6to4 embedded addresses.
    
    Returns:
        (True, "Public IP") if safe; otherwise (False, reason_string).
    """
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError as exc:
        return False, f"Invalid IP address format: {exc}"

    # Handle IPv4-mapped IPv6 (e.g. ::ffff:127.0.0.1, ::ffff:7f00:1)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped

    # Handle IPv4-compatible IPv6 (deprecated ::x.x.x.x)
    if isinstance(ip, ipaddress.IPv6Address) and ip.sixtofour is None:
        if (
            ip.packed[:12] == b"\x00" * 12
            and ip != ipaddress.ip_address("::")
            and ip != ipaddress.ip_address("::1")
        ):
            ip = ipaddress.IPv4Address(ip.packed[12:])

    # Handle 6to4 with private embedded IPv4 (2002::/16)
    if isinstance(ip, ipaddress.IPv6Address) and ip.sixtofour:
        embedded_v4 = ip.sixtofour
        v4_ok, v4_reason = is_public_ip(str(embedded_v4))
        if not v4_ok:
            return False, f"6to4 embedded private IP: {v4_reason}"

    # Standard property checks
    if ip.is_loopback:
        return False, "Loopback address"
    if ip.is_link_local:
        return False, "Link-local address"
    if ip.is_unspecified:
        return False, "Unspecified address"
    if ip.is_multicast:
        return False, "Multicast address"
    if ip.is_reserved:
        return False, "Reserved address"
    if ip.is_private:
        return False, "Private network address"

    # Explicit subnet containment checks
    for net in BLOCKED_NETWORKS:
        if ip in net:
            return False, f"Blocked network range {net}"

    if not ip.is_global:
        return False, "Not a globally routable unicast address"

    return True, "Public IP"


def validate_url_syntax(url_str: str) -> urllib.parse.ParseResult:
    """Validate URL scheme, ports, and absence of embedded credentials.
    
    Raises SafeFetchError on any syntax violation.
    """
    if not url_str or not isinstance(url_str, str) or len(url_str) > 4096:
        raise SafeFetchError("URL is empty, invalid, or exceeds maximum allowed length (4096 characters).")

    try:
        parsed = urllib.parse.urlparse(url_str)
    except Exception as exc:
        raise SafeFetchError(f"Malformed URL: {exc}") from exc

    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise SafeFetchError(f"Unsupported scheme '{parsed.scheme}'; only HTTP and HTTPS are permitted.")

    # Reject embedded credentials
    if parsed.username is not None or parsed.password is not None or "@" in (parsed.netloc or ""):
        raise SafeFetchError("URLs with embedded user credentials (username/password) are forbidden.")

    # Enforce standard ports only
    try:
        port = parsed.port
    except ValueError as exc:
        raise SafeFetchError(f"Invalid port in URL: {exc}") from exc

    if port is not None:
        if scheme == "http" and port != 80:
            raise SafeFetchError(f"Non-standard HTTP port {port} is forbidden (only port 80 allowed).")
        if scheme == "https" and port != 443:
            raise SafeFetchError(f"Non-standard HTTPS port {port} is forbidden (only port 443 allowed).")

    try:
        hostname = parsed.hostname
    except ValueError as exc:
        raise SafeFetchError(f"Invalid hostname in URL: {exc}") from exc

    if not hostname:
        raise SafeFetchError("URL must contain a valid hostname.")

    return parsed


async def default_system_dns_resolver(hostname: str) -> list[str]:
    """Resolve hostname using system DNS in a worker thread."""
    try:
        # Check if already IP literal
        ipaddress.ip_address(hostname)
        return [hostname]
    except ValueError:
        pass

    loop = asyncio.get_running_loop()
    try:
        addrinfo = await loop.getaddrinfo(
            hostname,
            None,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise SafeFetchError(f"DNS resolution failed for {hostname}: {exc}") from exc

    ips = list({entry[4][0] for entry in addrinfo if entry[4]})
    if not ips:
        raise SafeFetchError(f"DNS returned no IP addresses for {hostname}")
    return ips


class SafeNetworkBackend(AutoBackend):
    """Custom network backend that binds the socket to a validated public IP.
    
    Guarantees that DNS rebinding cannot redirect the connection to a private address.
    """

    def __init__(
        self,
        dns_resolver: Callable[[str], asyncio.Future[list[str]] | Any],
        underlying_backend: Any | None = None,
    ) -> None:
        super().__init__()
        self._dns_resolver = dns_resolver
        self._underlying_backend = underlying_backend
        self.last_connected_ip: str | None = None

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Any = None,
    ) -> httpcore.AsyncNetworkStream:
        """Resolve host, validate IP, and connect socket directly to the validated IP."""
        # Resolve destination
        if inspect.iscoroutinefunction(self._dns_resolver):
            ips = await self._dns_resolver(host)
        else:
            res = self._dns_resolver(host)
            ips = await res if asyncio.iscoroutine(res) else res

        if not ips:
            raise SafeFetchError(f"No IP addresses resolved for {host}")

        # Validate all returned IPs; reject if any is non-public
        for ip_cand in ips:
            is_ok, reason = is_public_ip(ip_cand)
            if not is_ok:
                raise SSRFBlockedError(
                    f"Destination {host} resolved to non-public IP {ip_cand} ({reason})"
                )

        last_exc: Exception | None = None
        for target_ip in ips:
            try:
                if self._underlying_backend is not None:
                    stream = await self._underlying_backend.connect_tcp(
                        host=target_ip,
                        port=port,
                        timeout=timeout,
                        local_address=local_address,
                        socket_options=socket_options,
                    )
                else:
                    stream = await super().connect_tcp(
                        host=target_ip,
                        port=port,
                        timeout=timeout,
                        local_address=local_address,
                        socket_options=socket_options,
                    )
                self.last_connected_ip = target_ip
                return stream
            except Exception as exc:
                last_exc = exc
                continue

        if last_exc is not None:
            raise last_exc
        raise SafeFetchError(f"No IP addresses could be reached for {host}")


class SafeAsyncHTTPTransport(httpx.AsyncHTTPTransport):
    """HTTPX transport configured with safe SSRF-blocking backend and no proxy inheritance."""

    def __init__(
        self,
        network_backend: SafeNetworkBackend,
        **kwargs: Any,
    ) -> None:
        # Enforce trust_env=False to prevent environment proxy bypassing
        super().__init__(trust_env=False, **kwargs)
        self.safe_backend = network_backend

        # Replace underlying pool with one bound to safe_backend
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=self._pool._ssl_context,
            max_connections=10,
            max_keepalive_connections=0,  # Do not keep connections alive across distinct fetches
            keepalive_expiry=0.0,
            http1=True,
            http2=False,
            network_backend=self.safe_backend,
            retries=0,
        )


class SafeFetcher:
    """Safe HTTP resource fetcher adhering to strict SSRF and resource bounds."""

    def __init__(
        self,
        max_redirects: int = DEFAULT_MAX_REDIRECTS,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        overall_timeout_seconds: float = DEFAULT_OVERALL_TIMEOUT_SECONDS,
        allowed_content_types: Sequence[str] = DEFAULT_ALLOWED_CONTENT_TYPES,
        dns_resolver: Callable[[str], Any] | None = None,
        custom_transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.max_redirects = max_redirects
        self.max_response_bytes = max_response_bytes
        self.overall_timeout_seconds = overall_timeout_seconds
        self.allowed_content_types = tuple(t.lower() for t in allowed_content_types)
        self._dns_resolver = dns_resolver or default_system_dns_resolver
        self._custom_transport = custom_transport

    async def fetch(self, url: str) -> RetrievedSource:
        """Fetch a web resource safely with full boundary enforcement.
        
        Returns:
            RetrievedSource containing fetch status and text if retrieved.
        """
        source_id = f"src_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        deadline = time.monotonic() + self.overall_timeout_seconds

        try:
            async with asyncio.timeout(max(0.001, self.overall_timeout_seconds)):
                return await self._fetch_internal(url=url, source_id=source_id, now_iso=now_iso, deadline=deadline)
        except (TimeoutError, asyncio.TimeoutError):
            return RetrievedSource(
                source_id=source_id,
                initial_url=url,
                final_url=url,
                redirect_count=0,
                status=SourceFetchState.INACCESSIBLE,
                fetched_at=now_iso,
                error_message=f"TIMEOUT: Overall fetch deadline of {self.overall_timeout_seconds}s exceeded.",
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return RetrievedSource(
                source_id=source_id,
                initial_url=url,
                final_url=url,
                redirect_count=0,
                status=SourceFetchState.INACCESSIBLE,
                fetched_at=now_iso,
                error_message=f"FETCH_ERROR: {exc}",
            )

    async def _fetch_internal(
        self, url: str, source_id: str, now_iso: str, deadline: float
    ) -> RetrievedSource:
        current_url = url
        redirect_count = 0
        last_resolved_ip: str | None = None

        while True:
            # 1. Overall deadline check
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return RetrievedSource(
                    source_id=source_id,
                    initial_url=url,
                    final_url=current_url,
                    redirect_count=redirect_count,
                    status=SourceFetchState.INACCESSIBLE,
                    fetched_at=now_iso,
                    error_message=f"TIMEOUT: Overall fetch deadline of {self.overall_timeout_seconds}s exceeded.",
                )

            # 2. Syntax and port validation
            try:
                parsed = validate_url_syntax(current_url)
            except SafeFetchError as exc:
                return RetrievedSource(
                    source_id=source_id,
                    initial_url=url,
                    final_url=current_url,
                    redirect_count=redirect_count,
                    status=SourceFetchState.INACCESSIBLE,
                    fetched_at=now_iso,
                    error_message=f"INVALID_URL: {exc}",
                )

            # 3. DNS resolution & SSRF precheck
            try:
                if inspect.iscoroutinefunction(self._dns_resolver):
                    ips = await self._dns_resolver(parsed.hostname)
                else:
                    res = self._dns_resolver(parsed.hostname)
                    ips = await res if asyncio.iscoroutine(res) else res

                for ip_cand in ips:
                    ok, reason = is_public_ip(ip_cand)
                    if not ok:
                        return RetrievedSource(
                            source_id=source_id,
                            initial_url=url,
                            final_url=current_url,
                            redirect_count=redirect_count,
                            resolved_ip=ip_cand,
                            status=SourceFetchState.SSRF_BLOCKED,
                            fetched_at=now_iso,
                            error_message=f"SSRF_BLOCKED: Destination {parsed.hostname} resolved to non-public IP {ip_cand} ({reason}).",
                        )
                last_resolved_ip = ips[0]
            except Exception as exc:
                return RetrievedSource(
                    source_id=source_id,
                    initial_url=url,
                    final_url=current_url,
                    redirect_count=redirect_count,
                    status=SourceFetchState.INACCESSIBLE,
                    fetched_at=now_iso,
                    error_message=f"DNS_ERROR: {exc}",
                )

            # 4. Check deadline after DNS and execute request with custom or bound transport
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return RetrievedSource(
                    source_id=source_id,
                    initial_url=url,
                    final_url=current_url,
                    redirect_count=redirect_count,
                    resolved_ip=last_resolved_ip,
                    status=SourceFetchState.INACCESSIBLE,
                    fetched_at=now_iso,
                    error_message=f"TIMEOUT: Overall fetch deadline of {self.overall_timeout_seconds}s exceeded after DNS resolution.",
                )

            backend = SafeNetworkBackend(dns_resolver=self._dns_resolver)
            transport = self._custom_transport or SafeAsyncHTTPTransport(network_backend=backend)

            try:
                async with httpx.AsyncClient(
                    transport=transport,
                    follow_redirects=False,
                    trust_env=False,
                    timeout=httpx.Timeout(remaining, connect=min(remaining, 10.0)),
                ) as client:
                    request = client.build_request(
                        "GET",
                        current_url,
                        headers={"User-Agent": USER_AGENT, "Accept": "text/html, text/plain;q=0.9, application/xhtml+xml"},
                    )
                    response = await client.send(request, stream=True)

                    if backend.last_connected_ip:
                        last_resolved_ip = backend.last_connected_ip

                    # Handle Redirects manually
                    if response.is_redirect:
                        await response.aclose()
                        redirect_count += 1
                        if redirect_count > self.max_redirects:
                            return RetrievedSource(
                                source_id=source_id,
                                initial_url=url,
                                final_url=current_url,
                                redirect_count=redirect_count,
                                resolved_ip=last_resolved_ip,
                                status=SourceFetchState.INACCESSIBLE,
                                http_status_code=response.status_code,
                                fetched_at=now_iso,
                                error_message=f"REDIRECT_LIMIT: Exceeded maximum allowed redirects ({self.max_redirects}).",
                            )

                        location = response.headers.get("location")
                        if not location:
                            return RetrievedSource(
                                source_id=source_id,
                                initial_url=url,
                                final_url=current_url,
                                redirect_count=redirect_count,
                                resolved_ip=last_resolved_ip,
                                status=SourceFetchState.INACCESSIBLE,
                                http_status_code=response.status_code,
                                fetched_at=now_iso,
                                error_message="INVALID_REDIRECT: Redirect response missing Location header.",
                            )

                        next_url = urllib.parse.urljoin(current_url, location)
                        current_url = next_url
                        continue  # Loop to validate next hop

                    # Non-redirect handling
                    try:
                        # Check HTTP status
                        if response.status_code >= 400:
                            await response.aclose()
                            return RetrievedSource(
                                source_id=source_id,
                                initial_url=url,
                                final_url=current_url,
                                redirect_count=redirect_count,
                                resolved_ip=last_resolved_ip,
                                status=SourceFetchState.INACCESSIBLE,
                                http_status_code=response.status_code,
                                fetched_at=now_iso,
                                error_message=f"HTTP_ERROR: Server returned status {response.status_code}.",
                            )

                        # Check Content-Type
                        content_type_raw = response.headers.get("content-type", "")
                        match = re.match(r"^([a-zA-Z0-9\-_]+/[a-zA-Z0-9\-_+.]+)", content_type_raw)
                        mime_type = match.group(1).lower() if match else ""

                        if mime_type not in self.allowed_content_types:
                            await response.aclose()
                            return RetrievedSource(
                                source_id=source_id,
                                initial_url=url,
                                final_url=current_url,
                                redirect_count=redirect_count,
                                resolved_ip=last_resolved_ip,
                                status=SourceFetchState.INACCESSIBLE,
                                http_status_code=response.status_code,
                                content_type=content_type_raw,
                                fetched_at=now_iso,
                                error_message=f"UNSUPPORTED_MIME: Content-Type '{content_type_raw}' is not permitted.",
                            )

                        # Check Content-Length header ceiling
                        content_length = response.headers.get("content-length")
                        if content_length and content_length.isdigit():
                            if int(content_length) > self.max_response_bytes:
                                await response.aclose()
                                return RetrievedSource(
                                    source_id=source_id,
                                    initial_url=url,
                                    final_url=current_url,
                                    redirect_count=redirect_count,
                                    resolved_ip=last_resolved_ip,
                                    status=SourceFetchState.INACCESSIBLE,
                                    http_status_code=response.status_code,
                                    content_type=content_type_raw,
                                    fetched_at=now_iso,
                                    error_message=f"OVERSIZED: Content-Length {content_length} exceeds {self.max_response_bytes} bytes.",
                                )

                        # Stream and enforce decompressed size ceiling
                        chunks: list[bytes] = []
                        total_bytes = 0

                        async for chunk in response.aiter_bytes():
                            # Check deadline while reading
                            if time.monotonic() > deadline:
                                await response.aclose()
                                return RetrievedSource(
                                    source_id=source_id,
                                    initial_url=url,
                                    final_url=current_url,
                                    redirect_count=redirect_count,
                                    resolved_ip=last_resolved_ip,
                                    status=SourceFetchState.INACCESSIBLE,
                                    fetched_at=now_iso,
                                    error_message="TIMEOUT: Fetch deadline exceeded while reading body.",
                                )

                            total_bytes += len(chunk)
                            if total_bytes > self.max_response_bytes:
                                await response.aclose()
                                return RetrievedSource(
                                    source_id=source_id,
                                    initial_url=url,
                                    final_url=current_url,
                                    redirect_count=redirect_count,
                                    resolved_ip=last_resolved_ip,
                                    status=SourceFetchState.INACCESSIBLE,
                                    http_status_code=response.status_code,
                                    content_type=content_type_raw,
                                    response_size_bytes=total_bytes,
                                    fetched_at=now_iso,
                                    error_message=f"OVERSIZED: Streamed body exceeded {self.max_response_bytes} byte cap.",
                                    extracted_text=None,
                                )
                            chunks.append(chunk)

                        raw_body = b"".join(chunks)
                        encoding = response.encoding or "utf-8"
                        try:
                            decoded_text = raw_body.decode(encoding, errors="replace")
                        except Exception:
                            decoded_text = raw_body.decode("utf-8", errors="replace")

                        return RetrievedSource(
                            source_id=source_id,
                            initial_url=url,
                            final_url=current_url,
                            redirect_count=redirect_count,
                            resolved_ip=last_resolved_ip,
                            status=SourceFetchState.RETRIEVED,
                            http_status_code=response.status_code,
                            content_type=content_type_raw,
                            response_size_bytes=total_bytes,
                            fetched_at=now_iso,
                            extracted_text=decoded_text,
                        )
                    finally:
                        await response.aclose()

            except (SSRFBlockedError, SafeFetchError) as exc:
                return RetrievedSource(
                    source_id=source_id,
                    initial_url=url,
                    final_url=current_url,
                    redirect_count=redirect_count,
                    resolved_ip=last_resolved_ip,
                    status=SourceFetchState.SSRF_BLOCKED,
                    fetched_at=now_iso,
                    error_message=str(exc),
                )
            except (httpx.TimeoutException, httpcore.TimeoutException):
                return RetrievedSource(
                    source_id=source_id,
                    initial_url=url,
                    final_url=current_url,
                    redirect_count=redirect_count,
                    resolved_ip=last_resolved_ip,
                    status=SourceFetchState.INACCESSIBLE,
                    fetched_at=now_iso,
                    error_message="TIMEOUT: Network timeout during connection or read.",
                )
            except Exception as exc:
                logger.warning("Fetch failed on %s: %s", current_url, exc)
                return RetrievedSource(
                    source_id=source_id,
                    initial_url=url,
                    final_url=current_url,
                    redirect_count=redirect_count,
                    resolved_ip=last_resolved_ip,
                    status=SourceFetchState.INACCESSIBLE,
                    fetched_at=now_iso,
                    error_message=f"NETWORK_ERROR: {exc}",
                )
