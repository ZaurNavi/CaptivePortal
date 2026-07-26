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
                throw new Error("Invalid portal counter response");
            }

            today.textContent = String(data.opened_today);
            total.textContent = String(data.opened_total);
            counter.hidden = false;
        })
        .catch(() => {
            counter.hidden = true;
        });
})();
