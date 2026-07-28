// Client-side filter for the quiz editor: with many questions, typing narrows
// the visible question blocks so the one you want to edit is quick to find.
// Loaded as an external file because the Content-Security-Policy forbids inline
// scripts (script-src 'self').
(function () {
    "use strict";

    var root = document.querySelector("[data-quiz-search]");
    var input = document.querySelector("[data-quiz-search-input]");
    var empty = document.querySelector("[data-quiz-search-empty]");
    var questions = document.querySelector("[data-quiz-questions]");
    if (!root || !input || !questions) {
        return;
    }

    // Text of one question block: its question text plus every answer.
    function haystack(block) {
        var fields = block.querySelectorAll('input[type="text"], input[type="search"]');
        var parts = [];
        for (var i = 0; i < fields.length; i++) {
            if (fields[i].value) {
                parts.push(fields[i].value);
            }
        }
        return parts.join("  ").toLowerCase();
    }

    function apply() {
        var query = input.value.trim().toLowerCase();
        var blocks = questions.querySelectorAll(".qblock");
        var visible = 0;
        for (var i = 0; i < blocks.length; i++) {
            var match = query === "" || haystack(blocks[i]).indexOf(query) !== -1;
            blocks[i].hidden = !match;
            if (match) {
                visible++;
            }
        }
        if (empty) {
            empty.hidden = !(query !== "" && visible === 0);
        }
    }

    // Hide the search entirely while there is nothing worth searching.
    function toggleSearchVisibility() {
        var count = questions.querySelectorAll(".qblock").length;
        root.hidden = count < 2;
        if (root.hidden && input.value) {
            input.value = "";
            apply();
        }
    }

    input.addEventListener("input", apply);

    // Removing a question block. Was an inline onclick, which the CSP blocks;
    // ask first when the block already has typed content so a stray click does
    // not silently discard a question.
    questions.addEventListener("click", function (event) {
        var button = event.target.closest("[data-remove-question]");
        if (!button) {
            return;
        }
        var block = button.closest("fieldset");
        if (!block) {
            return;
        }
        var typed = haystack(block).trim() !== "";
        if (typed && !window.confirm(button.getAttribute("data-remove-confirm") ||
                "Remove this question?")) {
            return;
        }
        block.remove();
    });

    // Questions get added (htmx) and removed (remove button) after load; keep
    // both the visibility of the search and the active filter in sync.
    var observer = new MutationObserver(function () {
        toggleSearchVisibility();
        if (input.value) {
            apply();
        }
    });
    observer.observe(questions, { childList: true });

    toggleSearchVisibility();
})();
