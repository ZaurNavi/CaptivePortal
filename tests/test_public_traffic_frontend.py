import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
SCRIPT = (
    ROOT
    / "app"
    / "web"
    / "static"
    / "js"
    / "portal_counter.js"
)
NODE_BINARY = os.environ.get("NODE_BINARY") or shutil.which("node")


def run_scenario(responses, assertions):
    if not NODE_BINARY:
        pytest.skip("Node.js is required for frontend behavior tests")
    source = SCRIPT.read_text(encoding="utf-8")
    harness = f"""
class Element {{
    constructor() {{
        this.hidden = true;
        this.textContent = "";
        this.dataset = {{}};
        this.children = {{}};
    }}
    querySelector(selector) {{
        return this.children[selector] || null;
    }}
}}

const counter = new Element();
counter.dataset.refreshSeconds = "60";
const today = new Element();
const total = new Element();
const traffic = new Element();
const trafficToday = new Element();
const trafficTotal = new Element();
counter.children["[data-portal-counter-today]"] = today;
counter.children["[data-portal-counter-total]"] = total;
counter.children["[data-public-traffic]"] = traffic;
counter.children["[data-public-traffic-today]"] = trafficToday;
counter.children["[data-public-traffic-total]"] = trafficTotal;

const document = {{
    querySelector(selector) {{
        return selector === "[data-portal-counter]" ? counter : null;
    }}
}};

const responseQueue = {json.dumps(responses)};
const fetchCalls = [];
async function fetch(url, options) {{
    fetchCalls.push({{url, options}});
    const payload = responseQueue.shift();
    return {{
        ok: true,
        async json() {{ return payload; }}
    }};
}}

const intervals = [];
const window = {{
    setInterval(callback, delay) {{
        intervals.push({{callback, delay}});
        return intervals.length;
    }}
}};

function assert(condition, message) {{
    if (!condition) throw new Error(message);
}}

{source}

(async () => {{
    await new Promise((resolve) => setImmediate(resolve));
    await new Promise((resolve) => setImmediate(resolve));
    {assertions}
    console.log("public traffic frontend scenario passed");
}})().catch((error) => {{
    console.error(error.stack || error);
    process.exitCode = 1;
}});
"""
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "public_traffic_frontend.js"
        path.write_text(harness, encoding="utf-8")
        completed = subprocess.run(
            [NODE_BINARY, str(path)],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    assert completed.returncode == 0, (
        f"Node frontend scenario failed:\n"
        f"{completed.stdout}\n{completed.stderr}"
    )


def valid_payload():
    return {
        "opened_today": 10,
        "opened_total": 100,
        "traffic": {
            "available": True,
            "ssid": "Zefer_Parki",
            "today_bytes": 3_407_872_000,
            "today_display": "3.17 GB",
            "total_bytes": 460_248_236_032,
            "total_display": "428.64 GB",
            "completed_sessions_today": 186,
            "completed_sessions_total": 18_342,
            "updated_at": "2026-07-29T08:00:00.000Z",
        },
    }


def test_valid_response_displays_both_sections():
    run_scenario(
        [valid_payload()],
        """
        assert(counter.hidden === false, "open counter hidden");
        assert(today.textContent === "10", "today opens not updated");
        assert(total.textContent === "100", "total opens not updated");
        assert(traffic.hidden === false, "traffic hidden");
        assert(
            trafficToday.textContent === "3.17 GB",
            "today traffic not updated"
        );
        assert(
            trafficTotal.textContent === "428.64 GB",
            "total traffic not updated"
        );
        assert(fetchCalls.length === 1, "unexpected fetch count");
        """,
    )


@pytest.mark.parametrize(
    "traffic",
    [
        {"available": False, "ssid": "Zefer_Parki"},
        {
            "available": True,
            "today_bytes": 1.5,
            "total_bytes": 2,
            "today_display": "1 MB",
            "total_display": "2 MB",
            "completed_sessions_today": 1,
            "completed_sessions_total": 2,
        },
        None,
    ],
)
def test_invalid_traffic_hides_only_traffic_section(traffic):
    payload = valid_payload()
    payload["traffic"] = traffic
    run_scenario(
        [payload],
        """
        assert(counter.hidden === false, "open counter was hidden");
        assert(today.textContent === "10", "open count unavailable");
        assert(traffic.hidden === true, "invalid traffic visible");
        """,
    )


def test_one_interval_refresh_updates_both_sections():
    second = valid_payload()
    second["opened_today"] = 11
    second["traffic"]["today_display"] = "4.5 GB"
    run_scenario(
        [valid_payload(), second],
        """
        assert(intervals.length === 1, "interval not singular");
        assert(intervals[0].delay === 60000, "interval is not 60s");
        intervals[0].callback();
        await new Promise((resolve) => setImmediate(resolve));
        await new Promise((resolve) => setImmediate(resolve));
        assert(fetchCalls.length === 2, "refresh did not fetch once");
        assert(today.textContent === "11", "opens not refreshed");
        assert(
            trafficToday.textContent === "4.5 GB",
            "traffic not refreshed"
        );
        """,
    )
