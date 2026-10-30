"""Required chaos tests against the real deployed stack."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.chaos
ROOT = Path(__file__).resolve().parents[2]


def run_experiment(filename):
    """Run a real experiment; preserve interactive browser-restart prompts."""
    result = subprocess.run(
        [sys.executable, str(ROOT / filename)],
        cwd=ROOT,
    )
    assert result.returncode == 0, f"{filename} did not finish successfully."


def test_database_failure_preserves_weather_and_restores_access():
    """Revoke the DB rule, restart weather, and verify graceful degradation."""
    run_experiment("experiment_database_failure.py")
    report = json.loads(
        (ROOT / "evidence/H7_database_failure.json").read_text()
    )
    (ROOT / "evidence/chaos_database_failure.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    outage = report["weather_during_outage"]
    assert outage["status"] == 200
    assert outage["body"]["cache"] == "unavailable"
    assert report["history_during_outage"]["status"] == 503
    assert report["after_restoration"]["status"] == 200
    assert report["after_restoration"]["body"]["cache"] in ("miss", "hit")


def test_weather_failure_returns_502_and_recovers_within_300_seconds():
    """Terminate weather and assert advisor behavior and timed recovery."""
    run_experiment("experiment_weather_recovery.py")
    report = json.loads(
        (ROOT / "evidence/H9_weather_recovery.json").read_text()
    )
    (ROOT / "evidence/chaos_weather_recovery.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    assert report["recovery_seconds"] <= 300
    assert report["replacement_instances"]
    assert any(
        row["advice_status"] == 502
        and row["advice_error"] == "weather_service_unavailable"
        and row["homepage_status"] == 200
        for row in report["advisor_observations"]
    )
