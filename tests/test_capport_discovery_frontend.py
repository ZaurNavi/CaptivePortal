import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from flask import Flask, render_template

from app.web.localization import PORTAL_TRANSLATIONS


ROOT = Path(__file__).parents[1]
TEMPLATE = ROOT / "app" / "web" / "templates" / "portal.html"
NODE_BINARY = os.environ.get("NODE_BINARY") or shutil.which("node")


def render_discovery_script(*, auto_retry=True, remaining_seconds=60):
    app = Flask(
        "capport-discovery-frontend-test",
        template_folder=str(TEMPLATE.parent),
    )
    with app.test_request_context("/capport/login"):
        html = render_template(
            "portal.html",
            session_id=None,
            redirect_url=None,
            initial_status="DISCOVERING_CLIENT",
            initial_progress=5,
            initial_state={
                "mode": "CAPPORT_DISCOVERY",
                "state": "DISCOVERING_CLIENT",
                "status": "DISCOVERING_CLIENT",
                "progress": 5,
                "terminal": False,
                "retryable": True,
            },
            portal_translations=PORTAL_TRANSLATIONS,
            portal_counter_visible=False,
            error_message=None,
            retry_url="/capport/login?wait_until=1060",
            restart_url="/capport/login",
            auto_retry=auto_retry,
            retry_interval_ms=2000,
            remaining_seconds=remaining_seconds,
        )
    scripts = re.findall(
        r"<script>(.*?)</script>",
        html,
        flags=re.DOTALL,
    )
    assert scripts
    return scripts[-1]


def run_scenario(scenario, *, auto_retry=True, remaining_seconds=60):
    if not NODE_BINARY:
        pytest.skip("Node.js is required for frontend behavior tests")

    harness = r"""
class ClassList {
    constructor() { this.values = new Set(); }
    add(...names) { names.forEach((name) => this.values.add(name)); }
    remove(...names) { names.forEach((name) => this.values.delete(name)); }
    contains(name) { return this.values.has(name); }
    toggle(name, force) {
        if (force === undefined) { force = !this.values.has(name); }
        if (force) { this.values.add(name); } else { this.values.delete(name); }
        return force;
    }
}

class Element {
    constructor() {
        this.classList = new ClassList();
        this.dataset = {};
        this.style = {};
        this.textContent = "";
        this.disabled = false;
        this.listeners = {};
        this.attributes = {};
    }
    addEventListener(name, callback) { this.listeners[name] = callback; }
    setAttribute(name, value) { this.attributes[name] = value; }
}

const requiredIds = [
    "progress-shell", "progress-bar", "progress-text",
    "progress-spinner", "connection-status", "portal-note",
    "portal-error", "retry-button"
];
const elements = Object.fromEntries(
    requiredIds.map((id) => [id, new Element()])
);
elements["retry-button"].classList.add("hidden");
const languageButtons = ["az", "ru", "en"].map((lang) => {
    const button = new Element();
    button.dataset.lang = lang;
    return button;
});
const document = {
    documentElement: {lang: "az"},
    getElementById(id) { return elements[id]; },
    querySelectorAll(selector) {
        return selector === ".lang-switcher button" ? languageButtons : [];
    }
};
const storage = new Map();
const localStorage = {
    getItem(key) { return storage.has(key) ? storage.get(key) : null; },
    setItem(key, value) { storage.set(key, String(value)); }
};

let now = 0;
const performance = {now() { return now; }};
let nextTimerId = 1;
const timeoutTimers = new Map();
const intervalTimers = new Map();
function fakeSetTimeout(callback, delay) {
    const id = nextTimerId++;
    timeoutTimers.set(id, {callback, delay});
    return id;
}
function fakeClearTimeout(id) { timeoutTimers.delete(id); }
function fakeSetInterval(callback, delay) {
    const id = nextTimerId++;
    intervalTimers.set(id, {callback, delay});
    return id;
}
function fakeClearInterval(id) { intervalTimers.delete(id); }
const clearTimeout = fakeClearTimeout;
const clearInterval = fakeClearInterval;

const locationCalls = [];
const windowEvents = {};
const window = {
    setTimeout: fakeSetTimeout,
    clearTimeout: fakeClearTimeout,
    setInterval: fakeSetInterval,
    clearInterval: fakeClearInterval,
    addEventListener(name, callback) { windowEvents[name] = callback; },
    close() {},
    location: {
        pathname: "/capport/login",
        replace(url) { locationCalls.push(url); }
    },
    crypto: {
        randomUUID() { return "11111111-1111-4111-8111-111111111111"; },
        getRandomValues(bytes) { bytes.fill(1); return bytes; }
    }
};

const fetchCalls = [];
function makeResponse(payload, status = 200) {
    return {
        status,
        ok: status >= 200 && status < 300,
        async json() { return payload; }
    };
}
function discoveryPayload(overrides = {}) {
    return {
        mode: "CAPPORT_DISCOVERY",
        state: "DISCOVERING_CLIENT",
        status: "DISCOVERING_CLIENT",
        progress: 5,
        terminal: false,
        retryable: true,
        auto_retry: true,
        remaining_seconds: 58,
        retry_interval_ms: 2000,
        retry_url: "/capport/login?wait_until=1060",
        restart_url: "/capport/login",
        ...overrides
    };
}
let fetchImpl = async () => makeResponse(discoveryPayload());
async function fetch(url, options = {}) {
    fetchCalls.push({url, options});
    return fetchImpl(url, options);
}
async function flushPromises() {
    await Promise.resolve();
    await Promise.resolve();
}
function runTimeoutWithDelay(delay) {
    const entry = Array.from(timeoutTimers.entries()).find(
        ([_id, timer]) => timer.delay === delay
    );
    if (!entry) { throw new Error(`No timeout with delay ${delay}`); }
    timeoutTimers.delete(entry[0]);
    entry[1].callback();
}
function assert(condition, message) {
    if (!condition) { throw new Error(message); }
}
function assertProgress(expected, message) {
    const expectedText = `${expected}%`;
    assert(
        elements["progress-text"].textContent === expectedText,
        `${message}: text=${elements["progress-text"].textContent}`
    );
    assert(
        elements["progress-bar"].style.width === expectedText,
        `${message}: width=${elements["progress-bar"].style.width}`
    );
    assert(
        elements["progress-shell"].attributes["aria-valuenow"]
            === String(expected),
        `${message}: aria=${elements["progress-shell"].attributes["aria-valuenow"]}`
    );
}
"""
    source = (
        harness
        + "\n"
        + render_discovery_script(
            auto_retry=auto_retry,
            remaining_seconds=remaining_seconds,
        )
        + "\n(async () => {\n"
        + scenario
        + "\nconsole.log('discovery scenario passed');\n"
        + "})().catch((error) => {\n"
        + "console.error(error.stack || error);\n"
        + "process.exitCode = 1;\n"
        + "});\n"
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        script_path = Path(temp_dir) / "capport_discovery_test.js"
        script_path.write_text(source, encoding="utf-8")
        completed = subprocess.run(
            [NODE_BINARY, str(script_path)],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

    assert completed.returncode == 0, (
        f"Node discovery scenario failed:\n"
        f"{completed.stdout}\n{completed.stderr}"
    )


def test_discovery_is_sequential_fetch_without_navigation():
    run_scenario(r"""
let resolveFirst;
fetchImpl = () => new Promise((resolve) => { resolveFirst = resolve; });
const first = requestDiscovery(discoveryRuntime.retryUrl, false);
const overlapping = requestDiscovery(discoveryRuntime.retryUrl, false);
await overlapping;
assert(fetchCalls.length === 1, "overlapping discovery fetch was started");
assert(discoveryRequestInFlight, "first discovery request is not active");
resolveFirst(makeResponse(discoveryPayload()));
await first;
assert(fetchCalls.length === 1, "discovery fetch was duplicated");
assert(discoveryRequestTimer !== null, "next fetch was not scheduled");
assert(locationCalls.length === 0, "discovery performed navigation");
""")


def test_discovery_progress_is_percent_monotonic_and_bounded():
    run_scenario(r"""
assertProgress(0, "new discovery cycle must start at zero");
assert(!elements["progress-text"].textContent.endsWith("s"),
    "discovery displayed seconds");

now = 30000;
renderState(currentState);
assertProgress(5, "half elapsed discovery cycle");
assert(displayedProgress >= 0 && displayedProgress <= 9,
    "discovery progress escaped its range");

applyDiscoveryEnvelope(discoveryPayload({remaining_seconds: 55}));
assertProgress(5, "later envelope moved discovery backwards");

now = 90000;
renderState(currentState);
assertProgress(9, "discovery deadline");
assert(displayedProgress <= 9, "discovery exceeded nine percent");

languageButtons[1].listeners.click();
assertProgress(9, "language change reset progress");
""")


def test_auth_session_response_updates_runtime_and_starts_polling():
    run_scenario(r"""
fetchImpl = async () => makeResponse({
    mode: "AUTH_SESSION",
    session_id: "session-1",
    redirect_url: null,
    initial_state: {
        session_id: "session-1",
        state: "WAITING",
        status: "WAITING",
        progress: 0,
        terminal: false,
        retryable: false
    }
});
await requestDiscovery(discoveryRuntime.retryUrl, false);
assert(sessionId === "session-1", "session id was not stored");
assert(!isDiscoveryMode, "discovery mode remained active");
assert(currentState.status === "WAITING", "initial state was not applied");
assertProgress(10, "auth transition with backend zero");
assert(discoveryRequestTimer === null, "discovery timer was not stopped");
assert(discoveryCountdownTimer === null, "countdown timer was not stopped");
assert(pollTimer !== null, "session polling was not scheduled");
assert(locationCalls.length === 0, "auth transition navigated the page");
""")


def test_auth_progress_mapping_is_monotonic_and_authorized_is_100():
    run_scenario(r"""
assert(authDisplayProgress(0, "WAITING") === 10, "0 must map to 10");
assert(authDisplayProgress(25, "AUTHORIZING") === 33,
    "25 must map to 33");
assert(authDisplayProgress(50, "VERIFYING") === 55,
    "50 must map to 55");
assert(authDisplayProgress(75, "VERIFYING") === 78,
    "75 must map to 78");
assert(authDisplayProgress(100, "VERIFYING") === 100,
    "100 must map to 100");

transitionToAuth({
    mode: "AUTH_SESSION",
    session_id: "session-1",
    redirect_url: null,
    initial_state: {
        session_id: "session-1",
        state: "WAITING",
        status: "WAITING",
        progress: 0,
        terminal: false,
        retryable: false
    }
});
assertProgress(10, "initial auth progress");

applyServerState({state: "AUTHORIZING", progress: 25});
assertProgress(33, "quarter auth progress");
applyServerState({state: "VERIFYING", progress: 50});
assertProgress(55, "half auth progress");
applyServerState({state: "VERIFYING", progress: 75});
assertProgress(78, "three-quarter auth progress");
applyServerState({state: "VERIFYING", progress: 25});
assertProgress(78, "lower polling result moved progress backwards");

applyServerState({
    state: "AUTHORIZED",
    progress: 1,
    authorized: true,
    terminal: true
});
assertProgress(100, "authorized progress");
""")


def test_controlled_500_auth_session_uses_authoritative_failed_state():
    run_scenario(r"""
fetchImpl = async () => makeResponse({
    mode: "AUTH_SESSION",
    session_id: "session-1",
    redirect_url: null,
    initial_state: {
        session_id: "session-1",
        state: "FAILED",
        status: "FAILED",
        progress: 100,
        terminal: false,
        retryable: true
    }
}, 500);
await requestDiscovery(discoveryRuntime.retryUrl, false);
assert(sessionId === "session-1", "controlled 500 lost the session");
assert(currentState.status === "FAILED", "failed state was not applied");
assert(currentState.retryable, "authoritative retryable was lost");
assert(!elements["retry-button"].classList.contains("hidden"),
    "retry button was not shown");
assert(locationCalls.length === 0, "controlled 500 navigated the page");
""")


def test_fast_authorized_response_uses_existing_success_redirect():
    run_scenario(r"""
fetchImpl = async () => makeResponse({
    mode: "AUTH_SESSION",
    session_id: "session-1",
    redirect_url: "https://example.test/after",
    initial_state: {
        session_id: "session-1",
        state: "AUTHORIZED",
        status: "AUTHORIZED",
        progress: 100,
        authorized: true,
        terminal: true,
        retryable: false
    }
});
await requestDiscovery(discoveryRuntime.retryUrl, false);
assert(currentState.status === "AUTHORIZED", "authorized state was not applied");
assertProgress(100, "fast authorized response");
assert(locationCalls.length === 0, "redirect happened before success delay");
runTimeoutWithDelay(900);
runTimeoutWithDelay(500);
assert(locationCalls[0] === "https://example.test/after",
    "existing authorized redirect was not preserved");
""")


def test_manual_retry_starts_new_fetch_cycle_without_navigation():
    run_scenario(r"""
let resolveRestart;
fetchImpl = () => new Promise((resolve) => { resolveRestart = resolve; });
elements["retry-button"].listeners.click();
assertProgress(0, "manual discovery restart");
assert(fetchCalls.length === 1, "manual retry did not fetch");
assert(fetchCalls[0].url === "/capport/login", "restart URL was not used");
assert(discoveryRequestInFlight, "manual retry request is not active");
assert(locationCalls.length === 0, "manual retry navigated the page");

resolveRestart(makeResponse(discoveryPayload({
    remaining_seconds: 60,
    auto_retry: true,
    retry_url: "/capport/login?wait_until=1120"
})));
await flushPromises();
await flushPromises();
assert(discoveryRuntime.autoRetry, "new bounded cycle was not started");
assertProgress(0, "new server discovery cycle");
assert(locationCalls.length === 0, "manual retry navigated the page");
""", auto_retry=False, remaining_seconds=0)


def test_auth_retry_resets_displayed_progress_to_10():
    run_scenario(r"""
transitionToAuth({
    mode: "AUTH_SESSION",
    session_id: "session-1",
    redirect_url: null,
    initial_state: {
        session_id: "session-1",
        state: "FAILED",
        status: "FAILED",
        progress: 100,
        terminal: false,
        retryable: true
    }
});
assertProgress(100, "failed auth progress");

fetchImpl = () => new Promise(() => {});
elements["retry-button"].listeners.click();
assert(currentState.status === "WAITING", "retry did not enter waiting");
assertProgress(10, "auth retry reset");
assert(fetchCalls.length === 1, "auth retry request was not sent");
assert(fetchCalls[0].options.method === "POST", "auth retry is not POST");
assert(locationCalls.length === 0, "auth retry navigated the page");
""")


def test_invalid_response_keeps_current_document_and_discovery_mode():
    run_scenario(r"""
fetchImpl = async () => makeResponse({
    mode: "AUTH_SESSION",
    session_id: "session-1",
    redirect_url: null,
    initial_state: {
        session_id: "different-session",
        state: "WAITING",
        status: "WAITING",
        terminal: false,
        retryable: false
    }
});
await requestDiscovery(discoveryRuntime.retryUrl, false);
assert(sessionId === null, "invalid response installed a session id");
assert(isDiscoveryMode, "invalid response left discovery mode");
assert(currentState.status === "DISCOVERING_CLIENT",
    "invalid response changed the state");
assert(locationCalls.length === 0, "invalid response navigated the page");
""")


def test_terminal_discovery_error_and_pagehide_stop_timers():
    run_scenario(r"""
fetchImpl = async () => makeResponse({
    mode: "CAPPORT_DISCOVERY",
    state: "FAILED",
    status: "FAILED",
    progress: 100,
    terminal: true,
    retryable: false,
    auto_retry: false,
    remaining_seconds: 0,
    retry_interval_ms: 2000,
    retry_url: null,
    restart_url: null,
    error: "client_not_allowed"
}, 403);
await requestDiscovery(discoveryRuntime.retryUrl, false);
assert(!isDiscoveryMode, "terminal error left discovery active");
assert(discoveryRequestTimer === null, "terminal error kept request timer");
assert(discoveryCountdownTimer === null, "terminal error kept countdown timer");
assert(currentState.status === "FAILED", "terminal error was not rendered");
windowEvents.pagehide();
assert(!pageActive, "pagehide did not deactivate the page");
assert(pollTimer === null, "pagehide kept polling timer");
assert(locationCalls.length === 0, "terminal error navigated the page");
""")
