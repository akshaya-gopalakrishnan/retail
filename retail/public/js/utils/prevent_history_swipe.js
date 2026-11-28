(() => {
    if (window.retail_history_swipe_guard) return;
    window.retail_history_swipe_guard = true;

    // Trackpad history navigation starts when a horizontal wheel gesture escapes
    // a scroll boundary. Keep normal horizontal scrolling inside tables/dialogs.
    document.addEventListener("wheel", (event) => {
        if (!event.cancelable || event.ctrlKey || event.defaultPrevented) return;
        if (Math.abs(event.deltaX) <= Math.abs(event.deltaY)) return;

        for (const element of event.composedPath()) {
            if (!(element instanceof Element)) continue;
            const style = getComputedStyle(element);
            if (!/^(auto|scroll|overlay)$/.test(style.overflowX)) continue;
            const extent = element.scrollWidth - element.clientWidth;
            if (extent <= 1) continue;
            const minimum = style.direction === "rtl" ? -extent : 0;
            const maximum = style.direction === "rtl" ? 0 : extent;
            if (event.deltaX < 0 && element.scrollLeft > minimum + 1) return;
            if (event.deltaX > 0 && element.scrollLeft < maximum - 1) return;
        }

        event.preventDefault();
    }, { passive: false, capture: true });
})();
