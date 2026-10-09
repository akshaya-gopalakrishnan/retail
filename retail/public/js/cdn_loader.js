(function () {
    const fallbacks = frappe.boot?.retail_cdn_local_assets;
    if (!fallbacks || window.__retailCdnLoader) return;
    window.__retailCdnLoader = true;
    const original = frappe.require;

    async function download(remote, local) {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 5000);
        try {
            const response = await fetch(remote, { credentials: "omit", signal: controller.signal });
            if (!response.ok) throw new Error(`Asset response ${response.status}`);
            return { content: await response.text(), url: remote };
        } catch (error) {
            const response = await fetch(local, { credentials: "same-origin" });
            if (!response.ok) throw new Error(`Local asset response ${response.status}`);
            return { content: await response.text(), url: new URL(local, window.location.origin).href };
        } finally {
            clearTimeout(timer);
        }
    }

    frappe.require = function (items, callback) {
        const paths = (typeof items === "string" ? [items] : items)
            .map(path => frappe.assets.bundled_asset(path));
        if (!paths.some(path => fallbacks[path])) return original.call(this, items, callback);
        frappe.dom.freeze();
        return Promise.all(paths.map(path => download(path, fallbacks[path] || path)))
            .then(contents => {
                paths.forEach((path, index) => {
                    let content = contents[index].content;
                    if (frappe.assets.extn(path) === "css") {
                        // Lazy styles are injected inline, so relative URLs need
                        // an explicit CDN base instead of the ERP page's URL.
                        content = content.replace(/url\(\s*(["']?)([^"')]+)\1\s*\)/g,
                            (match, quote, url) => /^(data:|#)/i.test(url.trim()) ? match :
                                `url("${new URL(url.trim(), contents[index].url).href}")`);
                    }
                    frappe.assets.eval_assets(path, content);
                });
                callback?.();
            }).finally(() => frappe.dom.unfreeze());
    };
})();
