from dataclasses import dataclass


@dataclass(frozen=True)
class LettaWebToolSpec:
    name: str
    description: str
    source_code: str
    return_char_limit: int = 12000
    tags: tuple[str, ...] = ("hannario", "web", "read-only")
    default_requires_approval: bool = False


FETCH_WEB_TEXT_SOURCE = r'''def fetch_web_text(url: str, max_chars: int = 4000) -> str:
    """Fetch a public web page and return compact readable text.

    Args:
        url: Public http or https URL to fetch.
        max_chars: Maximum returned text characters. Values are clamped to 200..10000.

    Returns:
        A compact text representation of the fetched page.
    """
    import ipaddress
    import re
    import socket
    import urllib.error
    import urllib.parse
    import urllib.request

    safe_max_chars = max(200, min(int(max_chars), 10000))
    parsed = urllib.parse.urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        return "Rejected URL: only http and https are allowed."
    if not parsed.hostname:
        return "Rejected URL: hostname is required."

    try:
        addresses = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as error:
        return f"Failed to resolve URL hostname: {error}"

    for address in addresses:
        ip_text = address[4][0]
        try:
            ip = ipaddress.ip_address(ip_text)
        except ValueError:
            return f"Rejected URL: could not validate resolved IP {ip_text}."
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return "Rejected URL: private, local, or reserved network addresses are not allowed."

    request = urllib.request.Request(
        urllib.parse.urlunparse(parsed),
        headers={"User-Agent": "hannario-v2/0.1 (+read-only web tool)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            content_type = response.headers.get("content-type", "")
            body = response.read(500_000)
            final_url = response.geturl()
            status = response.status
    except urllib.error.URLError as error:
        return f"Failed to fetch URL: {error}"

    encoding = "utf-8"
    match = re.search(r"charset=([^;\s]+)", content_type, flags=re.IGNORECASE)
    if match:
        encoding = match.group(1)
    text = body.decode(encoding, errors="replace")

    if "html" in content_type.lower() or re.search(r"<html[\s>]", text, flags=re.IGNORECASE):
        title_match = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.IGNORECASE | re.DOTALL)
        title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else ""
        text = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"&lt;", "<", text)
        text = re.sub(r"&gt;", ">", text)
        text = re.sub(r"&quot;", '"', text)
        text = re.sub(r"&#39;", "'", text)
    else:
        title = ""

    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > safe_max_chars:
        text = text[: safe_max_chars - 3].rstrip() + "..."

    lines = [
        "web_fetch_result:",
        f"status: {status}",
        f"url: {final_url}",
        f"content_type: {content_type or 'unknown'}",
    ]
    if title:
        lines.append(f"title: {title}")
    lines.extend(["text:", text or "(empty response body)"])
    return "\n".join(lines)
'''


LETTA_WEB_TOOL_SPECS = [
    LettaWebToolSpec(
        name="fetch_web_text",
        description="Fetch a public web page and return compact readable text.",
        source_code=FETCH_WEB_TEXT_SOURCE,
    ),
]
