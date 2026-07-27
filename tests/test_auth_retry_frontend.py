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
TEMPLATE = (
    ROOT / "app" / "web" / "templates" / "portal.html"
)
NODE_BINARY = os.environ.get("NODE_BINARY") or shutil.which("node")


def render_portal_script(initial_state):
    app = Flask(
        "retry-frontend-test",
        template_folder=str(TEMPLATE.parent),
    )
    with app.test_request_context("/"):
        html = render_template(
            "portal.html",
            session_id="test-session",
            redirect_url=None,
            initial_status=initial_state["state"],
            initial_progress=initial_state.get("progress", 0),
            initial_state=initial_state,
            portal_translations=PORTAL_TRANSLATIONS,
            portal_counter_visible=False,
            error_message=None,
        )
    scripts = re.findall(
        r"<script>(.*?)</script>",
        html,
        flags=re.DOTALL,
    )
    assert scripts
    return scripts[-1]


def run_frontend_scenario(initial_state, scenario):
    if not NODE_BINARY:
        pytest.skip("Node.js is required for frontend behavior tests")

    harness = r"""
class ClassList {
    constructor() {
        this.values = new Set();
    }
    add(...names) {
        names.forEach((name) => this.values.add(name));
    }
    remove(...names) {
        names.forEach((name) => this.values.delete(name));
    }
    toggle(name, force) {
        if (force === undefined) {
            force = !this.values.has(name);
        }
        if (force) {
            this.values.add(name);
        } else {
            this.values.delete(name);
        }
        return force;
    }
    contains(name) {
        return this.values.has(name);
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
    addEventListener(name, callback) {
        this.listeners[name] = callback;
    }
    setAttribute(name, value) {
        this.attributes[name] = value;
    }
}

const requiredIds = [
    "progress-shell",
    "progress-bar",
    "progress-text",
    "progress-spinner",
    "connection-status",
    "portal-note",
    "portal-error",
    "retry-button"
];
const elements = Object.fromEntries(
    requiredIds.map((id) => [id, new Element()])
);
elements["retry-button"].classList.add("hidden");

const fakeLangButtons = ["az", "ru", "en"].map((lang) => {
    const button = new Element();
    button.dataset.lang = lang;
    return button;
});

const document = {
    documentElement: {lang: "az"},
    getElementById(id) {
        return elements[id];
    },
    querySelectorAll(selector) {
        if (selector === ".lang-switcher button") {
            return fakeLangButtons;
        }
        return [];
    }
};

const storage = new Map();
const localStorage = {
    getItem(key) {
        return storage.has(key) ? storage.get(key) : null;
    },
    setItem(key, value) {
        storage.set(key, String(value));
    }
};

let nextTimerId = 1;
const scheduledTimers = new Map();
function fakeSetTimeout(callback, delay) {
    const id = nextTimerId++;
    scheduledTimers.set(id, {callback, delay});
    return id;
}
function fakeClearTimeout(id) {
    scheduledTimers.delete(id);
}

const window = {
    setTimeout: fakeSetTimeout,
    clearTimeout: fakeClearTimeout,
    close() {},
    location: {replace() {}},
    crypto: {
        randomUUID() {
            return "11111111-1111-4111-8111-111111111111";
        },
        getRandomValues(bytes) {
            bytes.fill(1);
            return bytes;
        }
    }
};
const clearTimeout = fakeClearTimeout;

const fetchCalls = [];
function makeResponse(state) {
    return {
        async json() {
            return state;
        }
    };
}
let fetchImpl = async () => makeResponse({
    state: "FAILED",
    status: "FAILED",
    progress: 100,
    retryable: true,
    terminal: false,
    authorized: false,
    current_run_number: 1
});
async function fetch(url, options = {}) {
    fetchCalls.push({url, options});
    return fetchImpl(url, options);
}

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}
"""
    source = (
        harness
        + "\n"
        + render_portal_script(initial_state)
        + "\n"
        + "(async () => {\n"
        + scenario
        + "\nconsole.log('frontend scenario passed');\n"
        + "})().catch((error) => {\n"
        + "console.error(error.stack || error);\n"
        + "process.exitCode = 1;\n"
        + "});\n"
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        script_path = Path(temp_dir) / "retry_frontend_test.js"
        script_path.write_text(source, encoding="utf-8")
        completed = subprocess.run(
            [NODE_BINARY, str(script_path)],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

    assert completed.returncode == 0, (
        f"Node frontend scenario failed:\n"
        f"{completed.stdout}\n{completed.stderr}"
    )


def test_approved_retry_localization_is_exact():
    assert PORTAL_TRANSLATIONS["az"]["retryButton"] == (
        "Yenidən cəhd et"
    )
    assert PORTAL_TRANSLATIONS["ru"]["retryButton"] == "Повторить"
    assert PORTAL_TRANSLATIONS["en"]["retryButton"] == "Try again"
    assert PORTAL_TRANSLATIONS["ru"]["retryableFailure"] == (
        "Не удалось завершить подключение. Нажмите «Повторить»."
    )
    assert PORTAL_TRANSLATIONS["ru"]["expiredNote"] == (
        "Сессия подключения истекла. Переподключитесь к Wi-Fi "
        "и снова откройте портал."
    )


def test_retry_ui_uses_one_post_and_state_reconciliation():
    template = TEMPLATE.read_text(encoding="utf-8")

    assert 'id="retry-button"' in template
    assert "retryButton.disabled = true;" in template
    assert "activeRetryRequestId = createRetryRequestId();" in template
    assert "retry_request_id: activeRetryRequestId" in template
    assert (
        "/auth/session/${encodeURIComponent(sessionId)}/retry"
        in template
    )
    assert "await reconcileRetryState();" in template
    assert "location.reload()" not in template
    assert "retryInFlight" in template


def test_retryable_and_final_failures_are_rendered_separately():
    template = TEMPLATE.read_text(encoding="utf-8")

    assert "if (state.retryable)" in template
    assert "showError(texts.retryableFailure);" in template
    assert "showError(texts.finalFailure);" in template
    assert '"RESETTING"' in template


def test_retryable_failure_button_and_click_transition():
    run_frontend_scenario(
        {
            "state": "FAILED",
            "progress": 100,
            "retryable": True,
            "terminal": False,
            "authorized": False,
            "current_run_number": 1,
        },
        r"""
const retryButtonElement = elements["retry-button"];
assert(
    !retryButtonElement.classList.contains("hidden"),
    "retry button must be visible for retryable failure"
);
assert(
    retryButtonElement.disabled === false,
    "retry button must be enabled for retryable failure"
);

let resolvePost;
fetchImpl = () => new Promise((resolve) => {
    resolvePost = () => resolve(makeResponse({
        state: "WAITING",
        progress: 0,
        retryable: false,
        terminal: false,
        authorized: false,
        current_run_number: 2
    }));
});

const clickPromise = retryButtonElement.listeners.click();
await Promise.resolve();
assert(
    retryButtonElement.disabled === true,
    "retry button must be disabled immediately"
);
assert(
    retryButtonElement.classList.contains("hidden"),
    "retry button must be hidden immediately"
);
assert(
    elements["progress-bar"].style.width === "0%",
    "retry must reset progress to zero"
);
assert(fetchCalls.length === 1, "click must issue exactly one request");
assert(
    fetchCalls[0].options.method === "POST",
    "retry request must use POST"
);

resolvePost();
await clickPromise;
assert(currentState.status === "WAITING", "new run must be active");
assert(
    retryButtonElement.classList.contains("hidden"),
    "button must stay hidden while the new run is active"
);
""",
    )


def test_lost_retry_response_reconciles_active_run():
    run_frontend_scenario(
        {
            "state": "FAILED",
            "progress": 100,
            "retryable": True,
            "terminal": False,
            "authorized": False,
            "current_run_number": 1,
        },
        r"""
fetchImpl = async (_url, options) => {
    if (options.method === "POST") {
        throw new Error("lost response");
    }
    return makeResponse({
        state: "AUTHORIZING",
        progress: 50,
        retryable: false,
        terminal: false,
        authorized: false,
        current_run_number: 2
    });
};

await elements["retry-button"].listeners.click();
assert(fetchCalls.length === 2, "retry must reconcile with one GET");
assert(fetchCalls[0].options.method === "POST", "first call is POST");
assert(fetchCalls[1].options.method === "GET", "second call is GET");
assert(
    currentState.status === "AUTHORIZING",
    "GET state must become authoritative"
);
assert(
    elements["retry-button"].classList.contains("hidden"),
    "button must not return for an active reconciled run"
);
assert(pollTimer !== null, "polling must continue after reconciliation");
""",
    )


def test_reset_response_keeps_polling_active():
    run_frontend_scenario(
        {
            "state": "FAILED",
            "progress": 100,
            "retryable": False,
            "terminal": True,
            "authorized": False,
            "current_run_number": 1,
        },
        r"""
pollTimer = window.setTimeout(() => {}, 1000);
const previousTimer = pollTimer;
applyServerState({
    state: "RESET",
    progress: 100,
    retryable: false,
    terminal: false,
    authorized: false,
    current_run_number: 1
});
assert(
    activeStatuses.has(currentState.status),
    "RESET must be treated as active compatibility state"
);
assert(
    pollTimer === previousTimer,
    "RESET must not stop an existing polling timer"
);

fetchImpl = async () => makeResponse({
    state: "RESET",
    progress: 100,
    retryable: false,
    terminal: false,
    authorized: false,
    current_run_number: 1
});
await pollSession();
assert(pollTimer !== null, "polling must be rescheduled after RESET");
""",
    )


def test_expired_response_hides_retry_and_stops_polling():
    run_frontend_scenario(
        {
            "state": "FAILED",
            "progress": 100,
            "retryable": True,
            "terminal": False,
            "authorized": False,
            "current_run_number": 1,
        },
        r"""
pollTimer = window.setTimeout(() => {}, 1000);
applyServerState({
    state: "EXPIRED",
    progress: 100,
    retryable: false,
    terminal: true,
    authorized: false,
    current_run_number: 1
});
assert(
    elements["retry-button"].classList.contains("hidden"),
    "retry button must be hidden for EXPIRED"
);
assert(
    elements["retry-button"].disabled === true,
    "retry button must be disabled for EXPIRED"
);
assert(pollTimer === null, "EXPIRED must stop polling");
""",
    )
