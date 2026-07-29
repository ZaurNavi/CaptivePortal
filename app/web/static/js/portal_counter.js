(() => {
    "use strict";

    const counter = document.querySelector(
        "[data-portal-counter]"
    );

    if (!counter) {
        return;
    }

    const today = counter.querySelector(
        "[data-portal-counter-today]"
    );
    const total = counter.querySelector(
        "[data-portal-counter-total]"
    );
    const traffic = counter.querySelector(
        "[data-public-traffic]"
    );
    const trafficToday = counter.querySelector(
        "[data-public-traffic-today]"
    );
    const trafficTotal = counter.querySelector(
        "[data-public-traffic-total]"
    );
    const refreshSeconds = Number.parseInt(
        counter.dataset.refreshSeconds || "60",
        10
    );
    const refreshMilliseconds = (
        Number.isInteger(refreshSeconds) && refreshSeconds > 0
            ? refreshSeconds
            : 60
    ) * 1000;

    const hideTraffic = () => {
        if (traffic) {
            traffic.hidden = true;
        }
    };

    const updateTraffic = (data) => {
        if (
            !traffic
            || !trafficToday
            || !trafficTotal
            || !data
            || data.available !== true
            || !Number.isInteger(data.today_bytes)
            || data.today_bytes < 0
            || !Number.isInteger(data.total_bytes)
            || data.total_bytes < 0
            || !Number.isInteger(data.completed_sessions_today)
            || data.completed_sessions_today < 0
            || !Number.isInteger(data.completed_sessions_total)
            || data.completed_sessions_total < 0
            || typeof data.today_display !== "string"
            || typeof data.total_display !== "string"
        ) {
            hideTraffic();
            return;
        }
        trafficToday.textContent = data.today_display;
        trafficTotal.textContent = data.total_display;
        traffic.hidden = false;
    };

    const refresh = () => {
        fetch("/api/public/portal-counter", {
            method: "GET",
            cache: "no-store",
            headers: {
                "Accept": "application/json"
            }
        })
            .then((response) => {
                if (!response.ok) {
                    throw new Error("Portal counter unavailable");
                }
                return response.json();
            })
            .then((data) => {
                if (
                    !Number.isInteger(data.opened_today)
                    || !Number.isInteger(data.opened_total)
                ) {
                    throw new Error(
                        "Invalid portal counter response"
                    );
                }

                today.textContent = String(data.opened_today);
                total.textContent = String(data.opened_total);
                counter.hidden = false;
                updateTraffic(data.traffic);
            })
            .catch(() => {
                counter.hidden = true;
                hideTraffic();
            });
    };

    refresh();
    window.setInterval(refresh, refreshMilliseconds);
})();
