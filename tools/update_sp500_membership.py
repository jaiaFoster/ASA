"""Capture the Founder-authorized current S&P 500 membership snapshot.

This is an explicit maintenance command, never a runtime network dependency.
It reads the current table from Wikipedia's MediaWiki API and writes one
effective-dated, revision-pinned JSON snapshot for review and commit.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PAGE_TITLE = "List_of_S&P_500_companies"
SOURCE_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
API_URL = "https://en.wikipedia.org/w/api.php"
EXPECTED_COLUMNS = (
    "Symbol",
    "Security",
    "GICS Sector",
    "GICS Sub-Industry",
    "Headquarters Location",
    "Date added",
    "CIK",
    "Founded",
)


class _FirstTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._table_depth = 0
        self._in_cell = False
        self._cell_parts: list[str] = []
        self._row: list[str] = []
        self.rows: list[list[str]] = []
        self._finished = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._finished:
            return
        if tag == "table":
            self._table_depth += 1
        elif self._table_depth == 1 and tag in {"th", "td"}:
            self._in_cell = True
            self._cell_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._finished:
            return
        if self._table_depth == 1 and tag in {"th", "td"} and self._in_cell:
            self._row.append(" ".join("".join(self._cell_parts).split()))
            self._in_cell = False
        elif self._table_depth == 1 and tag == "tr":
            if self._row:
                self.rows.append(self._row)
            self._row = []
        elif tag == "table" and self._table_depth:
            self._table_depth -= 1
            if self._table_depth == 0 and self.rows:
                self._finished = True


@dataclass(frozen=True)
class _PageRevision:
    revision_id: int
    published_at: str
    html: str


def _get_json(params: dict[str, str]) -> dict[str, Any]:
    request = Request(
        f"{API_URL}?{urlencode(params)}",
        headers={"User-Agent": "ASA/UNIVERSE-001 membership snapshot"},
    )
    with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed HTTPS authority
        return cast(dict[str, Any], json.loads(response.read()))


def _fetch_revision() -> _PageRevision:
    parsed = _get_json(
        {
            "action": "parse",
            "page": PAGE_TITLE,
            "prop": "text|revid",
            "format": "json",
            "formatversion": "2",
        }
    )["parse"]
    revision = _get_json(
        {
            "action": "query",
            "prop": "revisions",
            "titles": PAGE_TITLE,
            "rvprop": "ids|timestamp",
            "rvstartid": str(parsed["revid"]),
            "rvendid": str(parsed["revid"]),
            "format": "json",
            "formatversion": "2",
        }
    )["query"]["pages"][0]["revisions"][0]
    if revision["revid"] != parsed["revid"]:
        raise RuntimeError("Wikipedia revision changed during snapshot capture")
    return _PageRevision(parsed["revid"], revision["timestamp"], parsed["text"])


def _members(html: str) -> list[dict[str, str]]:
    parser = _FirstTableParser()
    parser.feed(html)
    if not parser.rows or tuple(parser.rows[0]) != EXPECTED_COLUMNS:
        raise RuntimeError("Wikipedia constituent table schema changed")
    members = [dict(zip(EXPECTED_COLUMNS, row, strict=True)) for row in parser.rows[1:]]
    symbols = [member["Symbol"] for member in members]
    if not 450 <= len(members) <= 550 or len(symbols) != len(set(symbols)):
        raise RuntimeError("Wikipedia constituent membership failed bounds or uniqueness checks")
    return members


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("screening/universe_snapshots"),
    )
    args = parser.parse_args()
    revision = _fetch_revision()
    published_at = datetime.fromisoformat(revision.published_at.replace("Z", "+00:00"))
    output = args.output_dir / f"sp500-{published_at.date().isoformat()}.json"
    payload = {
        "schema_version": "asa.equity_universe_membership/v1",
        "universe_id": "sp500",
        "source_name": "Wikipedia — List of S&P 500 companies",
        "source_url": SOURCE_URL,
        "source_revision_id": revision.revision_id,
        "published_at": revision.published_at,
        "effective_date": published_at.date().isoformat(),
        "members": _members(revision.html),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
