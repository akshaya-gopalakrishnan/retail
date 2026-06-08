(function(){
    function applyIconSprite() {
        document.querySelectorAll('.sidebar-item-container').forEach(container => {
            const iconContainer = container.querySelector('.sidebar-item-icon');
            if (!iconContainer) return;
            // If an SVG/use already exists, keep it
            if (iconContainer.querySelector('svg') || iconContainer.querySelector('use')) return;

            // Prefer explicit attribute "item-icon" if present
            let name = iconContainer.getAttribute('item-icon') || container.getAttribute('item-icon');
            // Fallback: try derive from label (lowercase, dash)
            if (!name) {
                const label_el = container.querySelector('.sidebar-item-label');
                const label = label_el?.innerText?.trim();
                if (label) {
                    name = label.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
                }
            }
            if (!name) return;

            // Create svg/use referring to the inlined icons sprite
            const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
            svg.setAttribute('class','icon  icon-md');
            svg.setAttribute('aria-hidden','true');

            const use = document.createElementNS('http://www.w3.org/2000/svg','use');
            // set both href and xlink:href for compatibility
            use.setAttribute('href', `#icon-${name}`);
            use.setAttributeNS('http://www.w3.org/1999/xlink','xlink:href', `#icon-${name}`);

            svg.appendChild(use);
            iconContainer.innerHTML = '';
            iconContainer.appendChild(svg);
        });
    }

    // Run on DOM ready and route changes
    function init() {
        applyIconSprite();
        frappe.router.on('change', () => setTimeout(applyIconSprite, 250));
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
