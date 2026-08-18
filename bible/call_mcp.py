"""
TheologAI MCP client — stateless HTTP (Streamable HTTP transport).
Each call is an independent POST; no session needed.

Usage:
    python call_mcp.py                        # run demo examples
    python call_mcp.py list                   # list all available tools
    python call_mcp.py commentary John 3:16   # commentary on a verse
    python call_mcp.py lookup John 3:16       # Bible verse lookup
"""

import json
import sys
import urllib.request
import urllib.error

MCP_URL = "https://mcp.theologai.xyz/mcp"


def _post(method: str, params: dict) -> dict:
    """Send one JSON-RPC 2.0 request and return the result."""
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }).encode()

    req = urllib.request.Request(
        MCP_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "TheologAI-Python-Client/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()}") from e

    # Server may return SSE (text/event-stream) or plain JSON
    content_type = ""
    if hasattr(resp, "headers"):
        content_type = resp.headers.get("Content-Type", "")

    if "text/event-stream" in content_type or raw.startswith("data:"):
        # Parse SSE: find the first "data: {...}" line
        for line in raw.splitlines():
            if line.startswith("data:"):
                raw = line[len("data:"):].strip()
                break

    data = json.loads(raw)

    if "error" in data:
        raise RuntimeError(f"MCP error: {json.dumps(data['error'], indent=2)}")

    return data.get("result", data)


def list_tools() -> list[dict]:
    result = _post("tools/list", {})
    return result.get("tools", [])


def call_tool(name: str, arguments: dict) -> str:
    result = _post("tools/call", {"name": name, "arguments": arguments})
    # Result is a list of content blocks
    parts = []
    for block in result.get("content", []):
        if block.get("type") == "text":
            parts.append(block["text"])
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Convenience wrappers
# ---------------------------------------------------------------------------

def bible_lookup(reference: str, translation: str = "ESV") -> str:
    return call_tool("bible_lookup", {"reference": reference, "translation": translation})


def commentary(reference: str, commentator: str = "Matthew Henry") -> str:
    """
    commentator options:
      "Matthew Henry" | "Jamieson-Fausset-Brown" | "Adam Clarke" |
      "John Gill"     | "Keil-Delitzsch"         | "Tyndale"
    """
    return call_tool("commentary_lookup", {"reference": reference, "commentator": commentator})


def cross_references(reference: str, limit: int = 10) -> str:
    return call_tool("bible_cross_references", {"reference": reference, "limit": limit})


def word_study(strongs_number: str) -> str:
    """e.g. strongs_number='G25' for agape"""
    return call_tool("original_language_lookup", {"strongs_number": strongs_number})


def parallel_passages(reference: str) -> str:
    return call_tool("parallel_passages", {"reference": reference})


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    args = sys.argv[1:]

    if not args or args[0] == "demo":
        print("=== Bible Lookup (John 3:16, ESV) ===")
        print(bible_lookup("John 3:16"))
        print()
        print("=== Matthew Henry Commentary (John 3:16) ===")
        print(commentary("John 3:16"))
        print()
        print("=== Cross References (John 3:16) ===")
        print(cross_references("John 3:16", limit=5))

    elif args[0] == "list":
        tools = list_tools()
        print(f"Available tools ({len(tools)}):\n")
        for t in tools:
            desc = t.get("description", "")[:80]
            print(f"  {t['name']:<35} {desc}")

    elif args[0] == "commentary" and len(args) >= 2:
        ref = " ".join(args[1:])
        print(commentary(ref))

    elif args[0] == "lookup" and len(args) >= 2:
        ref = " ".join(args[1:])
        print(bible_lookup(ref))

    elif args[0] == "xref" and len(args) >= 2:
        ref = " ".join(args[1:])
        print(cross_references(ref))

    elif args[0] == "word" and len(args) >= 2:
        print(word_study(args[1]))

    else:
        print(__doc__)


if __name__ == "__main__":
    main()
