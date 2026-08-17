from __future__ import annotations

from datetime import date

from screening.universe_membership import SP500_MEMBERSHIP


def test_sp500_snapshot_is_effective_dated_and_source_pinned() -> None:
    assert SP500_MEMBERSHIP.universe_id == "sp500"
    assert SP500_MEMBERSHIP.effective_date == date(2026, 8, 13)
    assert SP500_MEMBERSHIP.source_revision_id == 1369213082
    assert SP500_MEMBERSHIP.source_url == (
        "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    )


def test_sp500_snapshot_has_current_unique_membership() -> None:
    assert len(SP500_MEMBERSHIP.members) == 503
    assert len(set(SP500_MEMBERSHIP.symbols)) == 503
    assert {"AAPL", "BRK.B", "GOOG", "GOOGL", "MSFT"} <= set(SP500_MEMBERSHIP.symbols)


def test_existing_canonical_symbol_identity_is_sufficient() -> None:
    # Membership needs no parallel security identity. Even multi-class/dotted
    # symbols remain opaque normalized values under the existing symbol scheme.
    assert SP500_MEMBERSHIP.by_symbol["BRK.B"].security_name == "Berkshire Hathaway"
