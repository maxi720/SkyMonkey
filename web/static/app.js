// Site-wide behaviour that must not be inline: the Content-Security-Policy
// forbids inline scripts and inline event handlers (script-src 'self'), so an
// onsubmit="confirm(...)" attribute would simply never fire. Any form that
// carries a data-confirm message asks before it submits.
(function () {
    "use strict";

    document.addEventListener("submit", function (event) {
        var form = event.target;
        if (!form || !form.matches("[data-confirm]")) {
            return;
        }
        var message = form.getAttribute("data-confirm");
        if (message && !window.confirm(message)) {
            event.preventDefault();
        }
    });

    // Action buttons sit inside a <summary> so they stay visible while the quiz
    // accordion is collapsed. A click on a real control (link/button) must run
    // that control, not toggle the panel — so let those through untouched. A
    // click that only lands on the empty space of the actions area gets its
    // default (toggling the panel) cancelled.
    document.addEventListener("click", function (event) {
        if (!event.target.closest("[data-no-toggle]")) {
            return;
        }
        if (event.target.closest("a, button, input, label, select, textarea")) {
            return;
        }
        event.preventDefault();
    });

    // Test builder: a selection_mode radio (random / manual) shows only the
    // sections that match (marked data-mode="random" | "manual").
    function applyMode() {
        var checked = document.querySelector('input[name="selection_mode"]:checked');
        if (!checked) {
            return;
        }
        var sections = document.querySelectorAll("[data-mode]");
        for (var i = 0; i < sections.length; i++) {
            sections[i].hidden = sections[i].getAttribute("data-mode") !== checked.value;
        }
    }
    document.addEventListener("change", function (event) {
        if (event.target && event.target.name === "selection_mode") {
            applyMode();
        }
    });
    applyMode();  // app.js is deferred, so the DOM is already parsed

    // Test taking: a countdown. An element [data-countdown] carries the number
    // of seconds remaining; when it hits zero the test form auto-submits so a
    // late answer never counts. The server is still the authority on the
    // deadline — this is only the on-screen clock.
    var counter = document.querySelector("[data-countdown]");
    if (counter) {
        var remaining = parseInt(counter.getAttribute("data-countdown"), 10);
        var form = document.getElementById(counter.getAttribute("data-countdown-form"));
        var render = function () {
            if (remaining < 0) {
                remaining = 0;
            }
            var m = Math.floor(remaining / 60);
            var s = remaining % 60;
            counter.textContent = m + ":" + (s < 10 ? "0" : "") + s;
        };
        render();
        var tick = setInterval(function () {
            remaining -= 1;
            render();
            if (remaining <= 0) {
                clearInterval(tick);
                if (form) {
                    form.submit();
                }
            }
        }, 1000);
    }

    // ---------- topbar dropdown ----------
    // Uses a data-topbar-trigger attribute to avoid inline onclick (CSP).
    document.addEventListener("click", function (event) {
        var trigger = event.target.closest("[data-topbar-trigger]");
        if (!trigger) { return; }
        var dropdown = document.getElementById("topbarDropdown");
        if (!dropdown) { return; }
        var isOpen = !dropdown.hidden;
        dropdown.hidden = isOpen;
        trigger.setAttribute("aria-expanded", String(!isOpen));
        event.stopPropagation();
    });

    // Close the dropdown when clicking outside of it.
    document.addEventListener("click", function (event) {
        var menu = document.querySelector(".topbar-menu");
        if (!menu) { return; }
        var dropdown = document.getElementById("topbarDropdown");
        if (!dropdown || dropdown.hidden) { return; }
        if (!menu.contains(event.target)) {
            dropdown.hidden = true;
            var trigger = menu.querySelector(".topbar-menu-trigger");
            if (trigger) { trigger.setAttribute("aria-expanded", "false"); }
        }
    });

    // Close on Escape.
    document.addEventListener("keydown", function (event) {
        if (event.key !== "Escape") { return; }
        var dropdown = document.getElementById("topbarDropdown");
        if (!dropdown || dropdown.hidden) { return; }
        dropdown.hidden = true;
        var trigger = document.querySelector(".topbar-menu-trigger");
        if (trigger) {
            trigger.setAttribute("aria-expanded", "false");
            trigger.focus();
        }
    });

    // ---------- group list drag-and-drop ----------
    var groupList = document.getElementById("groupList");
    if (groupList) {
        var dragSrc = null;

        function getDragItems() {
            return Array.from(groupList.querySelectorAll(".group-item[draggable]"));
        }

        groupList.addEventListener("dragstart", function (event) {
            var item = event.target.closest(".group-item[draggable]");
            if (!item) { return; }
            dragSrc = item;
            item.classList.add("is-dragging");
            event.dataTransfer.effectAllowed = "move";
            event.dataTransfer.setData("text/plain", item.getAttribute("data-id") || "");
        });

        groupList.addEventListener("dragend", function () {
            getDragItems().forEach(function (el) {
                el.classList.remove("is-dragging", "is-drop-target");
            });
            dragSrc = null;
        });

        groupList.addEventListener("dragover", function (event) {
            event.preventDefault();
            event.dataTransfer.dropEffect = "move";
            var target = event.target.closest(".group-item[draggable]");
            getDragItems().forEach(function (el) {
                el.classList.toggle("is-drop-target", el === target && el !== dragSrc);
            });
        });

        groupList.addEventListener("dragleave", function (event) {
            var target = event.target.closest(".group-item[draggable]");
            if (!target) {
                getDragItems().forEach(function (el) {
                    el.classList.remove("is-drop-target");
                });
            }
        });

        groupList.addEventListener("drop", function (event) {
            event.preventDefault();
            var target = event.target.closest(".group-item[draggable]");
            if (!target || !dragSrc || target === dragSrc) { return; }

            // Insert dragSrc before or after target.
            var items = getDragItems();
            var srcIdx = items.indexOf(dragSrc);
            var tgtIdx = items.indexOf(target);
            if (srcIdx < tgtIdx) {
                groupList.insertBefore(dragSrc, target.nextSibling);
            } else {
                groupList.insertBefore(dragSrc, target);
            }

            // Persist new order to the server.
            var reorderUrl = groupList.getAttribute("data-reorder-url");
            if (reorderUrl) {
                var order = getDragItems().map(function (el) {
                    return el.getAttribute("data-id");
                });
                fetch(reorderUrl, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ order: order }),
                }).catch(function () {
                    // Reorder is best-effort; a failed save doesn't break the UI.
                });
            }
        });
    }
})();

