from __future__ import annotations

import json

import pytest

from screening.cli import main

AS_OF = "2026-07-22T16:00:00+00:00"


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


class TestFailClosed:
    def test_live_flag_fails_closed_and_never_reaches_the_runner(self, capsys, monkeypatch) -> None:
        def _fail(*_args, **_kwargs):
            raise AssertionError("--live must never reach run_screening")

        monkeypatch.setattr("screening.cli.run_screening", _fail)
        exit_code = main(["--live"])
        assert exit_code == 2
        assert "not yet available" in capsys.readouterr().err

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
