"""
HelloAO Bible Commentary API — verse-by-verse client.
Free, no API key, ~45M requests/month in production.

Endpoint: https://bible.helloao.org/api/c/{commentary}/{book}/{chapter}.json

Available commentaries:
  john-gill             — 29,707 verse entries, verse-by-verse (best coverage)
  jamieson-fausset-brown— 17,056 verse entries, verse-by-verse
  tyndale               — 15,757 verse entries, verse-by-verse
  adam-clarke           — 13,318 verse entries, verse-by-verse
  matthew-henry         —  4,124 entries, grouped by passage (not true verse-by-verse)
  john-calvin           —  7,332 verse entries
  keil-delitzsch        —  6,516 verse entries, OT only

Usage:
    python helloao_commentary.py John 3:16
    python helloao_commentary.py John 3:16 --all
    python helloao_commentary.py Rom 8:28 --commentary john-gill
    python helloao_commentary.py Gen 1:1 --commentary keil-delitzsch
    python helloao_commentary.py list-commentaries
    python helloao_commentary.py list-books john-gill
"""

import json
import sys
import urllib.request
import urllib.error
import re

BASE_URL = "https://bible.helloao.org/api"

# Maps common book name abbreviations → HelloAO book ID
BOOK_IDS = {
    # OT
    "genesis": "GEN", "gen": "GEN",
    "exodus": "EXO", "exo": "EXO", "ex": "EXO",
    "leviticus": "LEV", "lev": "LEV",
    "numbers": "NUM", "num": "NUM",
    "deuteronomy": "DEU", "deu": "DEU", "deut": "DEU",
    "joshua": "JOS", "jos": "JOS", "josh": "JOS",
    "judges": "JDG", "jdg": "JDG", "judg": "JDG",
    "ruth": "RUT", "rut": "RUT",
    "1 samuel": "1SA", "1sa": "1SA", "1sam": "1SA",
    "2 samuel": "2SA", "2sa": "2SA", "2sam": "2SA",
    "1 kings": "1KI", "1ki": "1KI",
    "2 kings": "2KI", "2ki": "2KI",
    "1 chronicles": "1CH", "1ch": "1CH", "1chr": "1CH",
    "2 chronicles": "2CH", "2ch": "2CH", "2chr": "2CH",
    "ezra": "EZR", "ezr": "EZR",
    "nehemiah": "NEH", "neh": "NEH",
    "esther": "EST", "est": "EST",
    "job": "JOB",
    "psalms": "PSA", "psa": "PSA", "psalm": "PSA", "ps": "PSA",
    "proverbs": "PRO", "pro": "PRO", "prov": "PRO",
    "ecclesiastes": "ECC", "ecc": "ECC", "eccl": "ECC",
    "song of solomon": "SNG", "sng": "SNG", "song": "SNG", "ss": "SNG",
    "isaiah": "ISA", "isa": "ISA",
    "jeremiah": "JER", "jer": "JER",
    "lamentations": "LAM", "lam": "LAM",
    "ezekiel": "EZK", "ezk": "EZK", "ezek": "EZK",
    "daniel": "DAN", "dan": "DAN",
    "hosea": "HOS", "hos": "HOS",
    "joel": "JOL", "jol": "JOL",
    "amos": "AMO", "amo": "AMO",
    "obadiah": "OBA", "oba": "OBA",
    "jonah": "JON", "jon": "JON",
    "micah": "MIC", "mic": "MIC",
    "nahum": "NAM", "nam": "NAM",
    "habakkuk": "HAB", "hab": "HAB",
    "zephaniah": "ZEP", "zep": "ZEP",
    "haggai": "HAG", "hag": "HAG",
    "zechariah": "ZEC", "zec": "ZEC", "zech": "ZEC",
    "malachi": "MAL", "mal": "MAL",
    # NT
    "matthew": "MAT", "mat": "MAT", "matt": "MAT",
    "mark": "MRK", "mrk": "MRK",
    "luke": "LUK", "luk": "LUK",
    "john": "JHN", "jhn": "JHN",
    "acts": "ACT", "act": "ACT",
    "romans": "ROM", "rom": "ROM",
    "1 corinthians": "1CO", "1co": "1CO", "1cor": "1CO",
    "2 corinthians": "2CO", "2co": "2CO", "2cor": "2CO",
    "galatians": "GAL", "gal": "GAL",
    "ephesians": "EPH", "eph": "EPH",
    "philippians": "PHP", "php": "PHP", "phil": "PHP",
    "colossians": "COL", "col": "COL",
    "1 thessalonians": "1TH", "1th": "1TH", "1thess": "1TH",
    "2 thessalonians": "2TH", "2th": "2TH", "2thess": "2TH",
    "1 timothy": "1TI", "1ti": "1TI", "1tim": "1TI",
    "2 timothy": "2TI", "2ti": "2TI", "2tim": "2TI",
    "titus": "TIT", "tit": "TIT",
    "philemon": "PHM", "phm": "PHM",
    "hebrews": "HEB", "heb": "HEB",
    "james": "JAS", "jas": "JAS",
    "1 peter": "1PE", "1pe": "1PE", "1pet": "1PE",
    "2 peter": "2PE", "2pe": "2PE", "2pet": "2PE",
    "1 john": "1JN", "1jn": "1JN",
    "2 john": "2JN", "2jn": "2JN",
    "3 john": "3JN", "3jn": "3JN",
    "jude": "JUD", "jud": "JUD",
    "revelation": "REV", "rev": "REV",
}


def _get(url: str) -> dict:
    """Fetch JSON from HelloAO API."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "HelloAO-Python-Client/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} fetching {url}") from e


def parse_reference(reference: str) -> tuple[str, int, int | None]:
    """
    Parse 'John 3:16' → ('JHN', 3, 16)
    Parse 'John 3'    → ('JHN', 3, None)
    """
    # Handle "1 John 3:16" style (book name may start with digit)
    m = re.match(
        r'^(\d?\s*[A-Za-z]+(?:\s+[A-Za-z]+)?)\s+(\d+)(?::(\d+))?$',
        reference.strip()
    )
    if not m:
        raise ValueError(f"Cannot parse reference: {reference!r}  (expected 'Book Chapter[:Verse]')")

    book_raw = m.group(1).strip().lower()
    chapter = int(m.group(2))
    verse = int(m.group(3)) if m.group(3) else None

    book_id = BOOK_IDS.get(book_raw)
    if not book_id:
        raise ValueError(
            f"Unknown book: {m.group(1)!r}\n"
            f"Try one of: John, Rom, Gen, Ps, Matt, Rev, ..."
        )
    return book_id, chapter, verse


def get_verse_commentary(
    reference: str,
    commentary_id: str = "john-gill",
) -> str:
    """
    Fetch commentary for a specific verse or chapter.
    Returns formatted text.

    Args:
        reference:      e.g. 'John 3:16' or 'John 3'
        commentary_id:  e.g. 'john-gill', 'jamieson-fausset-brown', 'adam-clarke'
    """
    book_id, chapter, verse = parse_reference(reference)
    url = f"{BASE_URL}/c/{commentary_id}/{book_id}/{chapter}.json"
    data = _get(url)

    content = data["chapter"]["content"]
    commentary_name = data.get("commentary", {}).get("englishName", commentary_id)
    ref_label = f"{data['book'].get('commonName', data['book']['name'])} {chapter}"
    if verse:
        ref_label += f":{verse}"

    if verse is None:
        # Return full chapter
        lines = [f"**{commentary_name} — {ref_label}**\n"]
        for item in content:
            if item["type"] == "verse":
                v_num = item["number"]
                v_text = "\n".join(item["content"])
                lines.append(f"**v.{v_num}** {v_text}\n")
        return "\n".join(lines)
    else:
        # Find the verse entry that covers this verse number.
        # Some commentaries (Matthew Henry) group ranges under the first verse number.
        # We return the entry whose number is <= verse and is the closest match.
        best = None
        for item in content:
            if item["type"] == "verse" and item["number"] <= verse:
                best = item
            elif item["type"] == "verse" and item["number"] > verse:
                break

        if best is None:
            return f"No commentary found for {ref_label} in {commentary_name}."

        v_text = "\n".join(best["content"])
        note = ""
        if best["number"] != verse:
            note = f" [note: this commentary entry starts at v.{best['number']}]"

        return f"**{commentary_name} — {ref_label}**{note}\n\n{v_text}"


def get_all_commentaries(reference: str) -> str:
    """Fetch verse commentary from all 7 commentaries and return combined output."""
    all_ids = [
        "john-gill",
        "jamieson-fausset-brown",
        "adam-clarke",
        "john-calvin",
        "matthew-henry",
        "tyndale",
        "keil-delitzsch",
    ]
    results = []
    for cid in all_ids:
        try:
            text = get_verse_commentary(reference, cid)
            results.append(text)
        except RuntimeError as e:
            results.append(f"**{cid}** — skipped: {e}")
    return "\n\n" + ("=" * 60) + "\n\n".join(results)


def list_commentaries() -> None:
    data = _get(f"{BASE_URL}/available_commentaries.json")
    print(f"{'ID':<30} {'Verses':>7}  {'Books':>5}  Name")
    print("-" * 80)
    for c in data["commentaries"]:
        print(
            f"{c['id']:<30} {c['totalNumberOfVerses']:>7}  "
            f"{c['numberOfBooks']:>5}  {c['englishName']}"
        )


def list_books(commentary_id: str) -> None:
    data = _get(f"{BASE_URL}/c/{commentary_id}/books.json")
    books = data.get("books", [])
    print(f"Books in {commentary_id} ({len(books)} total):\n")
    for b in books:
        print(f"  {b['id']:<6} {b['englishName']}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    args = sys.argv[1:]

    if not args:
        print(__doc__)
        return

    if args[0] == "list-commentaries":
        list_commentaries()
        return

    if args[0] == "list-books" and len(args) >= 2:
        list_books(args[1])
        return

    # Parse flags
    commentary_id = "john-gill"
    fetch_all = False
    ref_parts = []

    i = 0
    while i < len(args):
        if args[i] == "--commentary" and i + 1 < len(args):
            commentary_id = args[i + 1]
            i += 2
        elif args[i] == "--all":
            fetch_all = True
            i += 1
        else:
            ref_parts.append(args[i])
            i += 1

    reference = " ".join(ref_parts)

    if not reference:
        print(__doc__)
        return

    if fetch_all:
        print(get_all_commentaries(reference))
    else:
        print(get_verse_commentary(reference, commentary_id))


if __name__ == "__main__":
    main()
