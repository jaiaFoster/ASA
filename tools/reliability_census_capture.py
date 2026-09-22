"""Emit a sanitized, read-only production reliability census.

No payloads, credentials, account data, or provider request IDs are written.
The artifact contains aggregate latest-state and acquisition diagnostics plus
bounded subject examples only for ASA-owned defects requiring correction.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from sqlalchemy import text

from asa.config import Settings
from asa.integrations.postgres import create_postgres_engine
from asa.integrations.universal_screening_postgres import PostgresLatestResultRepository
from screening.universe_membership import SP500_MEMBERSHIP
from strategy_runtime.health import build_strategy_health
from strategy_runtime.reliability_census import _classify_result_reason
from strategy_runtime.result import EvaluationState, UniversalScreeningResult


def _reason(row: UniversalScreeningResult) -> str:
    blockers = row.blockers
    if blockers:
        return blockers[0]
    temporal = row.temporal
    if temporal is not None and temporal.usability_reason:
        return temporal.usability_reason
    warnings = row.warnings
    return warnings[0] if warnings else "untyped_missing_data"


def capture() -> dict[str, object]:
    settings = Settings()
    engine = create_postgres_engine(settings.database_url)
    rows = PostgresLatestResultRepository(engine).get_all()
    active_symbols = frozenset(SP500_MEMBERSHIP.symbols)
    active = tuple(row.to_result() for row in rows if row.symbol in active_symbols)
    identities = sorted(f"{row.strategy_id}:{row.symbol}" for row in active)

    strategy_counts: dict[str, object] = {}
    owner_counts: Counter[str] = Counter()
    asa_owned_examples: dict[str, set[str]] = {}
    reason_counts: Counter[str] = Counter()
    freshness_counts: Counter[str] = Counter()
    for strategy_id in sorted({row.strategy_id for row in active}):
        strategy_rows = tuple(row for row in active if row.strategy_id == strategy_id)
        funnel = build_strategy_health(strategy_id, strategy_rows)
        strategy_counts[strategy_id] = {
            "subjects": funnel.active_subjects,
            "evaluated": funnel.evaluated,
            "missing_data": funnel.missing_data,
            "no_signal": funnel.no_signal,
            "pass": funnel.passed,
            "watch": funnel.watch,
            "typed_unknown_counts": dict(funnel.typed_unknown_counts),
        }
        for row in strategy_rows:
            if row.temporal is not None:
                freshness_counts[row.temporal.freshness_status] += 1
            if row.evaluation_state is EvaluationState.MISSING_DATA:
                reason = _reason(row)
                classification, owner = _classify_result_reason(reason)
                reason_counts[f"{strategy_id}:{reason}"] += 1
                owner_counts[f"{owner.value}:{classification.value}"] += 1
                if owner.value == "asa_owned":
                    asa_owned_examples.setdefault(classification.value, set()).add(row.symbol)

    captured_at = datetime.now(UTC)
    cutoff = captured_at - timedelta(hours=24)
    with engine.connect() as connection:
        attempt_rows = connection.execute(
            text("""
                SELECT capability, outcome, COALESCE(diagnostic_code, 'success') AS diagnostic,
                       COUNT(*) AS count
                FROM screening_acquisition_attempts
                WHERE recorded_at >= :cutoff
                GROUP BY capability, outcome, COALESCE(diagnostic_code, 'success')
                ORDER BY capability, outcome, diagnostic
            """),
            {"cutoff": cutoff},
        ).mappings()
        attempt_counts = {
            f"{row['capability']}:{row['outcome']}:{row['diagnostic']}": int(row["count"])
            for row in attempt_rows
        }

    return {
        "schema_version": 1,
        "production_sha": settings.release_sha or "unknown",
        "captured_at": captured_at.isoformat(),
        "active_universe": {
            "id": SP500_MEMBERSHIP.universe_id,
            "effective_date": SP500_MEMBERSHIP.effective_date.isoformat(),
            "member_count": len(active_symbols),
        },
        "active_identity_count": len(identities),
        "active_identity_checksum": sha256("\n".join(identities).encode()).hexdigest(),
        "retained_nonactive_count": sum(row.symbol not in active_symbols for row in rows),
        "per_strategy": strategy_counts,
        "missingness_ownership": dict(sorted(owner_counts.items())),
        "asa_owned_examples": {
            key: sorted(symbols)[:10] for key, symbols in sorted(asa_owned_examples.items())
        },
        "missingness_reasons": dict(sorted(reason_counts.items())),
        "freshness": dict(sorted(freshness_counts.items())),
        "acquisition_attempts_last_24h": attempt_counts,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    artifact = capture()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    print(f"reliability census written: {args.output}")


if __name__ == "__main__":
    main()
