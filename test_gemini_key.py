"""Test Gemini without saving or displaying the API key."""
import getpass
import json
from pathlib import Path
import warnings

import requests


def main():
    """Read configuration, securely prompt for a key, and test Gemini."""
    settings = {}
    for line in Path(".env").read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            settings[name.strip()] = value.strip().strip("\"'")

    model = settings["GEMINI_MODEL"]
    warnings.simplefilter("error", getpass.GetPassWarning)
    key = getpass.getpass("Paste Gemini API key (hidden), then press Enter: ").strip()
    if not key:
        raise SystemExit("No key entered. Run the script again.")

    try:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={"x-goog-api-key": key},
            json={
                "contents": [{
                    "parts": [{
                        "text": "Suggest what to wear in 45 F weather with light rain, in one sentence."
                    }]
                }]
            },
            timeout=30,
        )
    except requests.RequestException:
        raise SystemExit("Connection failed or timed out. No key was saved.")
    finally:
        key = None

    print(f"Model: {model}")
    print(f"HTTP status: {response.status_code}")

    if not response.ok:
        raise SystemExit(
            "Test failed. Share only the model and HTTP status above; "
            "do not share your key."
        )

    data = response.json()
    text = "\n".join(
        part.get("text", "")
        for candidate in data.get("candidates", [])
        for part in candidate.get("content", {}).get("parts", [])
    ).strip()

    if not text:
        raise SystemExit("No answer returned. Tell me this result.")

    result = {"model": model, "status": response.status_code, "answer": text}
    Path("evidence").mkdir(exist_ok=True)
    Path("evidence/C2_gemini_test.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(f"Answer: {text}")
    print("Test output saved. API key was not saved.")


if __name__ == "__main__":
    main()
