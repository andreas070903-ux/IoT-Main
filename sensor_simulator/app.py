"""Generate wind turbine sensor measurements and send them to the IoT REST API."""

import argparse
import json
import math
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from turbine_control.state import TURBINE_IDS


def control_api_url(api_url: str, turbine_id: str) -> str:
    """Build the simulated turbine control endpoint from a measurements URL."""
    measurements_suffix = "/measurements"
    api_root = api_url.rstrip("/")
    if api_root.endswith(measurements_suffix):
        api_root = api_root[: -len(measurements_suffix)]
    return f"{api_root}/turbines/{turbine_id}/control"


def turbine_is_running(api_url: str, turbine_id: str) -> bool:
    """Read the simulated control state before generating a measurement."""
    url = control_api_url(api_url, turbine_id)
    try:
        with urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach API at {url}: {exc.reason}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("API returned invalid turbine control data.") from exc

    if (
        not isinstance(data, dict)
        or data.get("Turbine_ID") != turbine_id
        or data.get("status") not in {"RUNNING", "STOPPED"}
    ):
        raise RuntimeError("API returned turbine control data in an unexpected format.")
    return data["status"] == "RUNNING"


def generate_measurement(turbine_id: str) -> dict[str, Any]:
    """Generate one plausible wind turbine measurement."""
    wind_speed = round(random.uniform(1.47, 13.32), 2)
    expected_power = round(min(3000, (wind_speed / 12) ** 3 * 2000), 1)
    power_output = round(
        min(3000, expected_power * random.uniform(0.9, 1.05)), 1
    )
    alarm = random.random() < 0.01
    warning = not alarm and random.random() < 0.02

    return {
        "Timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "Turbine_ID": turbine_id,
        "Wind_Speed_m_s": wind_speed,
        "Wind_Direction_deg": round(random.uniform(131.3, 319.4), 1),
        "Ambient_Temp_C": round(random.uniform(-5, 25), 1),
        "Rotor_Speed_RPM": round(wind_speed * random.uniform(0.9, 1.1), 2),
        "Power_Output_kW": power_output,
        "Expected_Power_kW": expected_power,
        "Gearbox_Temp_C": round(
            random.uniform(36.6, 48) + power_output / 3000 * 20, 1
        ),
        "Generator_Temp_C": round(
            random.uniform(41.2, 55) + power_output / 3000 * 18, 1
        ),
        "Vibration_mm_s": round(
            random.uniform(2.0, 2.53) if alarm else random.uniform(1.3, 2.0), 2
        ),
        "Alarm_Flag": alarm,
        "Status": "ALARM" if alarm else "WARNING" if warning else "OK",
        "Maintenance_Required": "YES" if alarm else "NO",
    }


def non_negative_float(value: str) -> float:
    """Parse a finite, non-negative interval in seconds."""
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if not math.isfinite(parsed) or parsed < 0:
        raise argparse.ArgumentTypeError("must be a finite number zero or greater")
    return parsed


def non_negative_int(value: str) -> int:
    """Parse a non-negative number of records."""
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return parsed


def simulate(
    api_url: str,
    interval: float,
    repeat: bool,
    limit: int,
) -> int:
    """Generate and send sensor measurements to the API at the requested interval."""
    sent = 0
    try:
        while True:
            for turbine_id in TURBINE_IDS:
                if limit and sent >= limit:
                    return sent

                if not turbine_is_running(api_url, turbine_id):
                    print(
                        f"Skipping {turbine_id}: stopped in the simulation.",
                        file=sys.stderr,
                        flush=True,
                    )
                    if (repeat or sent < len(TURBINE_IDS)) and (
                        not limit or sent < limit
                    ):
                        time.sleep(interval)
                    continue

                record = generate_measurement(turbine_id)

                request = Request(
                    api_url,
                    data=json.dumps(record).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                try:
                    if urlparse(request.full_url).scheme not in ("http", "https"):
                        raise ValueError("Kun http og https er tilladt")

                    with urlopen(request, timeout=10) as response:  # nosec B310
                        if response.status != 201:
                            raise RuntimeError(
                                f"API returned unexpected HTTP status {response.status}"
                            )
                except HTTPError as exc:
                    detail = exc.read().decode("utf-8", errors="replace")
                    if exc.code == 409:
                        print(
                            f"Skipping {turbine_id}: stopped in the simulation.",
                            file=sys.stderr,
                            flush=True,
                        )
                        continue
                    raise RuntimeError(
                        f"API returned HTTP {exc.code}: {detail}"
                    ) from exc
                except URLError as exc:
                    raise RuntimeError(f"Could not reach API at {api_url}: {exc.reason}") from exc

                sent += 1
                print(
                    f"{sent}: {record['Timestamp']} | {record['Turbine_ID']} "
                    f"| {record['Status']}",
                    file=sys.stderr,
                    flush=True,
                )

                if (repeat or sent < len(TURBINE_IDS)) and (not limit or sent < limit):
                    time.sleep(interval)

            if not repeat or (limit and sent >= limit):
                return sent
    except KeyboardInterrupt:
        print(f"\nSimulation stopped after {sent} record(s).", file=sys.stderr)
        return sent


def main() -> int:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    parser = argparse.ArgumentParser(
        description="Generate wind turbine sensor data and send it to the IoT REST API."
    )
    parser.add_argument(
        "--api-url",
        default=os.environ.get("API_URL", "http://127.0.0.1:8000/measurements"),
        help="API measurement endpoint (default: http://127.0.0.1:8000/measurements)",
    )
    parser.add_argument(
        "--interval",
        type=non_negative_float,
        default=5.0,
        help="seconds between records (default: 5; use 0 for no delay)",
    )
    parser.add_argument(
        "--repeat",
        action="store_true",
        help="keep generating and sending measurements until stopped with Ctrl+C",
    )
    parser.add_argument(
        "--limit",
        type=non_negative_int,
        default=0,
        help="maximum records to send (default: 0 means no limit)",
    )
    args = parser.parse_args()

    try:
        sent = simulate(
            args.api_url,
            args.interval,
            args.repeat,
            args.limit,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Simulation complete. Sent {sent} record(s).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
