from __future__ import annotations

import json

import pytest

from market_data.transport import ReadOnlyTransportError
from screening.cli import APPROVED_LIVE_UNIVERSE, main

AS_OF = "2026-07-22T16:00:00+00:00"

# No test here ever sets a real credential -- clearing these first makes
# every --live test's "no provider available" behavior independent of
# whatever the host environment happens to have configured.
_PROVIDER_ENV_VARS = (
    "ASA_TRADIER_ACCESS_TOKEN",
    "TRADIER_ACCESS_TOKEN",
    "ASA_TRADIER_ENABLED",
    "ASA_FINNHUB_API_KEY",
    "FINNHUB_API_KEY",
    "ASA_FINNHUB_ENABLED",
    "ASA_ALPHA_VANTAGE_API_KEY",
    "ALPHA_VANTAGE_API_KEY",
    "ASA_ALPHA_VANTAGE_ENABLED",
    "ASA_DETERMINISTIC_FIXTURE_ENABLED",
)


def _clear_provider_env(monkeypatch) -> None:
    for name in _PROVIDER_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


class _NetworkFreeTransport:
    """Never performs real network I/O -- fails every request immediately,
    the same shape a real transport failure would take. Enough to prove
    --live's wiring (config -> provider -> per-symbol adapters -> results)
    works end to end without a live CLI test ever touching a real host.
    """

    def get(self, _request):
        raise ReadOnlyTransportError("test transport never performs real network I/O")


def _enable_one_live_provider(monkeypatch) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
    monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "test-token-not-a-real-credential")
    monkeypatch.setattr("screening.cli.build_live_transport", lambda _provider_id: _NetworkFreeTransport())


class TestDryRun:
    def test_dry_run_lists_all_registered_strategies_and_exits_zero(self, capsys) -> None:
        exit_code = main(["--dry-run", "--as-of", AS_OF, "--json"])
        assert exit_code == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["dry_run"] is True
        assert {entry["strategy_id"] for entry in payload["plan"]} == {
            "earnings_calendar",
            "forward_factor",
            "skew_momentum",
        }

    def test_dry_run_executes_nothing(self, capsys, monkeypatch) -> None:
        def _fail(*_args, **_kwargs):
            raise AssertionError("dry_run must never execute a strategy")

        monkeypatch.setattr("screening.cli.run_screening", _fail)
        exit_code = main(["--dry-run", "--as-of", AS_OF])
        assert exit_code == 0

    def test_dry_run_can_be_scoped_to_one_strategy(self, capsys) -> None:
        exit_code = main(["--dry-run", "--as-of", AS_OF, "--json", "--strategies", "forward_factor"])
        assert exit_code == 0
        payload = json.loads(capsys.readouterr().out)
        assert [entry["strategy_id"] for entry in payload["plan"]] == ["forward_factor"]


class TestRealRun:
    def test_all_ready_strategies_run_by_default_and_exit_zero(self, capsys) -> None:
        exit_code = main(["--as-of", AS_OF, "--json"])
        assert exit_code == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["dry_run"] is False
        assert {result["strategy_id"] for result in payload["results"]} == {
            "earnings_calendar",
            "forward_factor",
            "skew_momentum",
        }
        assert all(result["outcome_status"] == "pass" for result in payload["results"])

    def test_json_flag_suppresses_the_human_summary(self, capsys) -> None:
        main(["--as-of", AS_OF, "--json"])
        out = capsys.readouterr().out
        assert "SCREENING RUN" not in out
        json.loads(out)  # the whole stdout is valid JSON, nothing else was printed

    def test_default_mode_prints_a_human_summary_before_the_json(self, capsys) -> None:
        main(["--as-of", AS_OF])
        out = capsys.readouterr().out
        assert "SCREENING RUN" in out
        last_line = out.strip().splitlines()[-1]
        json.loads(last_line)

    def test_output_contains_no_evidence_of_a_raw_provider_payload(self, capsys) -> None:
        main(["--as-of", AS_OF, "--json"])
        out = capsys.readouterr().out
        assert "http://" not in out and "https://" not in out
        assert "Bearer" not in out and "Authorization" not in out


class TestLive:
    def test_no_enabled_live_provider_fails_closed_not_a_crash(self, capsys, monkeypatch) -> None:
        _clear_provider_env(monkeypatch)
        exit_code = main(["--live", "--universe", "AAPL", "--as-of", AS_OF])
        assert exit_code == 2
        assert "requires at least one enabled live provider" in capsys.readouterr().err

    def test_fixture_alone_does_not_count_as_an_enabled_live_provider(self, capsys, monkeypatch) -> None:
        # The fixture provider defaults to enabled (market_data/config.py's
        # own safety default) and, being alphabetically first, would
        # otherwise be tried before any real provider by CapabilityRegistry's
        # deterministic priority order -- silently serving every --live
        # request from offline fixture data. --live must force it out of the
        # provider pool regardless, so with no *real* provider configured
        # this must still fail closed, not quietly "succeed" via the fixture.
        _clear_provider_env(monkeypatch)
        monkeypatch.setenv("ASA_DETERMINISTIC_FIXTURE_ENABLED", "true")
        exit_code = main(["--live", "--universe", "AAPL", "--as-of", AS_OF])
        assert exit_code == 2
        assert "requires at least one enabled live provider" in capsys.readouterr().err

    def test_one_enabled_provider_runs_the_default_live_universe(self, capsys, monkeypatch) -> None:
        _enable_one_live_provider(monkeypatch)
        exit_code = main(["--live", "--as-of", AS_OF, "--json"])
        assert exit_code == 0
        payload = json.loads(capsys.readouterr().out)
        # One StrategyAdapterError-raising failure per strategy per symbol --
        # runner.py reports "unknown" subject_identity for adapter-raised
        # failures (no subject was ever resolved), so per-symbol iteration is
        # verified by result count, not by echoed identity.
        assert len(payload["results"]) == len(APPROVED_LIVE_UNIVERSE) * 3
        # The injected transport fails every request -- proves acquisition
        # actually ran through the live path (never the offline fixture).
        assert all(result["outcome_status"] == "missing_data" for result in payload["results"])

    def test_can_be_scoped_to_a_subset_of_the_live_universe(self, capsys, monkeypatch) -> None:
        _enable_one_live_provider(monkeypatch)
        exit_code = main(["--live", "--universe", "AAPL", "--as-of", AS_OF, "--json"])
        assert exit_code == 0
        payload = json.loads(capsys.readouterr().out)
        assert len(payload["results"]) == 3
        assert all(result["outcome_status"] == "missing_data" for result in payload["results"])

    def test_live_universe_symbol_rejected_without_live_flag(self, capsys) -> None:
        exit_code = main(["--universe", "SPY", "--as-of", AS_OF])
        assert exit_code == 2
        assert "unsupported universe" in capsys.readouterr().err

    def test_fixture_only_universe_symbol_rejected_with_live_flag(self, capsys, monkeypatch) -> None:
        _clear_provider_env(monkeypatch)
        exit_code = main(["--live", "--universe", "TSLA", "--as-of", AS_OF])
        assert exit_code == 2
        assert "unsupported universe" in capsys.readouterr().err

    def test_output_contains_no_evidence_of_a_raw_provider_payload(self, capsys, monkeypatch) -> None:
        _enable_one_live_provider(monkeypatch)
        exit_code = main(["--live", "--universe", "AAPL", "--as-of", AS_OF, "--json"])
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "http://" not in out and "https://" not in out
        assert "Bearer" not in out and "Authorization" not in out
        assert "test-token-not-a-real-credential" not in out


class TestFailClosed:
    def test_unknown_strategy_id_fails_closed(self, capsys) -> None:
        exit_code = main(["--strategies", "does_not_exist", "--as-of", AS_OF])
        assert exit_code == 2
        assert "unknown strategy_id" in capsys.readouterr().err

    def test_unsupported_universe_symbol_fails_closed(self, capsys) -> None:
        exit_code = main(["--universe", "TSLA", "--as-of", AS_OF])
        assert exit_code == 2
        assert "unsupported universe" in capsys.readouterr().err

    def test_empty_universe_fails_closed(self, capsys) -> None:
        exit_code = main(["--universe", "", "--as-of", AS_OF])
        assert exit_code == 2

    def test_naive_as_of_fails_closed(self, capsys) -> None:
        exit_code = main(["--as-of", "2026-07-22T16:00:00"])
        assert exit_code == 2
        assert "timezone-aware" in capsys.readouterr().err

    def test_malformed_as_of_fails_closed(self, capsys) -> None:
        exit_code = main(["--as-of", "not-a-date"])
        assert exit_code == 2
        assert "not a valid ISO8601" in capsys.readouterr().err

    def test_bad_arguments_exit_nonzero_via_argparse(self) -> None:
        with pytest.raises(SystemExit) as excinfo:
            main(["--not-a-real-flag"])
        assert excinfo.value.code != 0


class TestDeterminism:
    def test_identical_as_of_produces_identical_json_output(self, capsys) -> None:
        main(["--as-of", AS_OF, "--json"])
        first = capsys.readouterr().out
        main(["--as-of", AS_OF, "--json"])
        second = capsys.readouterr().out
        assert first == second

    def test_no_as_of_still_completes_and_uses_the_real_clock(self, capsys) -> None:
        exit_code = main(["--json"])
        assert exit_code == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["results"][0]["as_of"]
