"""Check both deployed tiers through the ALB."""
import argparse
import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from stack.config import load_dotenv


def get(url):
    """Return HTTP status and parsed response, including HTTP errors."""
    try:
        response = requests.get(url, timeout=75)
    except requests.RequestException:
        return 0, {"error": "connection_failed"}
    try:
        body = response.json()
    except ValueError:
        body = response.text
    return response.status_code, body


def run_checks(zip_code="60616"):
    """Run the nine checks; return their results for CLI or pytest."""
    settings = load_dotenv(ROOT / ".env")
    outputs = load_dotenv(ROOT / "stack_outputs.env")
    host = outputs["ALB_DNS_NAME"]
    weather = f"http://{host}:{settings['WEATHER_LISTENER_PORT']}"
    advisor = f"http://{host}:{settings['ADVISOR_LISTENER_PORT']}"
    results = []

    def check(name, ok, detail=""):
        results.append((name, bool(ok)))
        print(f"{'PASS' if ok else 'FAIL'}: {name} {detail}", flush=True)

    status, body = get(f"{weather}/weather?zip={zip_code}")
    check("weather returns a forecast",
          status == 200 and isinstance(body, dict) and "forecast" in body,
          f"HTTP {status}")

    status, body = get(f"{weather}/weather?zip={zip_code}")
    check("repeat request is a cache hit",
          status == 200 and isinstance(body, dict)
          and body.get("cache") == "hit",
          f"HTTP {status}")

    status, body = get(f"{weather}/history")
    check("history contains saved lookups",
          status == 200 and isinstance(body, dict)
          and body.get("count", 0) >= 1,
          f"HTTP {status}")

    status, _ = get(f"{weather}/weather?zip=abc")
    check("weather rejects invalid ZIP", status == 400, f"HTTP {status}")

    status, _ = get(f"{weather}/weather?zip=00000")
    check("weather rejects unknown ZIP", status == 404, f"HTTP {status}")

    status, body = get(f"{advisor}/advice?zip={zip_code}")
    advice_ok = (
        status == 200 and isinstance(body, dict) and bool(body.get("advice"))
    )
    check("advisor returns advice", advice_ok, f"HTTP {status}")
    check("advice comes from Gemini",
          advice_ok and body.get("source") == "gemini")

    if advice_ok:
        evidence = ROOT / "evidence"
        evidence.mkdir(exist_ok=True)
        (evidence / f"G2_advice_{zip_code}.json").write_text(
            json.dumps(body, indent=2), encoding="utf-8"
        )
        print("Source:", body.get("source"))
        print("Advice:", body["advice"])

    status, _ = get(f"{advisor}/advice?zip=abc")
    check("advisor rejects invalid ZIP", status == 400, f"HTTP {status}")

    status, body = get(f"{advisor}/")
    check("advisor homepage loads",
          status == 200 and isinstance(body, str) and "<form" in body,
          f"HTTP {status}")

    print(f"\n{sum(ok for _, ok in results)} of {len(results)} checks passed")
    print("Advisor page:", advisor + "/")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", default="60616")
    arguments = parser.parse_args()
    results = run_checks(arguments.zip)
    sys.exit(0 if all(ok for _, ok in results) else 1)
