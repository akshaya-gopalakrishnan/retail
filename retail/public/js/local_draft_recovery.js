(function () {
	if (window.__retail_local_draft_recovery_booted) return;
	window.__retail_local_draft_recovery_booted = true;

	const DB_NAME = "retail_local_draft_recovery";
	const DB_VERSION = 1;
	const STORE_NAME = "drafts";
	const CRITICAL_EXPIRY_MS = 48 * 60 * 60 * 1000;
	const SMALL_FORM_EXPIRY_MS = 12 * 60 * 60 * 1000;
	const CRITICAL_SAVE_DELAY_MS = 30000;
	const SMALL_FORM_SAVE_DELAY_MS = 5000;
	const MAX_DRAFT_BYTES = 8 * 1024 * 1024;
	const MAX_SMALL_FORM_ROWS = 250;
	const MAX_FULL_DOC_ROWS = 500;
	const CRITICAL_DOCTYPES = [
		"Sales Invoice",
		"Purchase Invoice",
		"Purchase Receipt",
		"Delivery Note",
		"Stock Entry",
		"Stock Reconciliation",
		"Sales Order",
		"Purchase Order",
	];
	const SMALL_FORM_DOCTYPES = [
		"Item",
		"Customer",
		"Supplier",
		"Item Price",
		"Item Group",
		"Brand",
		"UOM",
		"Warehouse",
		"Price List",
		"Address",
		"Contact",
		"Customer Group",
		"Supplier Group",
		"Territory",
		"Sales Person",
		"Sales Partner",
		"Mode of Payment",
		"Payment Terms Template",
		"Terms and Conditions",
		"Tax Category",
		"Item Tax Template",
		"Sales Taxes and Charges Template",
		"Purchase Taxes and Charges Template",
	];
	const TRACKED_DOCTYPES = Array.from(new Set([...CRITICAL_DOCTYPES, ...SMALL_FORM_DOCTYPES]));

	function boot() {
		if (!window.frappe?.ui?.form) {
			setTimeout(boot, 150);
			return;
		}
		registerHandlers();
		cleanupOldDrafts();
		exposeDebugTools();
	}

	function registerHandlers() {
		TRACKED_DOCTYPES.forEach((doctype) => {
			frappe.ui.form.on(doctype, {
				refresh(frm) {
					if (!shouldTrack(frm)) return;
					cleanupOldDrafts();
					offerRecovery(frm);
					if (isCriticalDoctype(frm.doctype) && canUseFullDocDraft(frm)) {
						setupAutoSaveLoop(frm);
					}
					scheduleDraftSave(frm);
				},
				after_save(frm) {
					deleteDraft(frm);
				},
				on_submit(frm) {
					deleteDraft(frm);
				},
				before_discard(frm) {
					deleteDraft(frm);
				},
			});
		});

		$(document).on("form-dirty", () => {
			const frm = window.cur_frm;
			if (shouldTrack(frm)) scheduleDraftSave(frm);
		});

		document.addEventListener("visibilitychange", () => {
			if (document.visibilityState !== "hidden") return;
			const frm = window.cur_frm;
			if (shouldTrack(frm) && frm.is_dirty?.() && canUseFullDocDraft(frm)) saveDraft(frm);
		});
	}

	function shouldTrack(frm) {
		return !!(frm?.doctype && TRACKED_DOCTYPES.includes(frm.doctype) && frm.doc && !frm.doc.__unsaved_recovered_prompt);
	}

	function getExpiryMs(doctype) {
		return CRITICAL_DOCTYPES.includes(doctype) ? CRITICAL_EXPIRY_MS : SMALL_FORM_EXPIRY_MS;
	}

	function getSaveDelayMs(doctype) {
		return isCriticalDoctype(doctype) ? CRITICAL_SAVE_DELAY_MS : SMALL_FORM_SAVE_DELAY_MS;
	}

	function isCriticalDoctype(doctype) {
		return CRITICAL_DOCTYPES.includes(doctype);
	}

	function scheduleDraftSave(frm) {
		if (frm?.__retail_local_draft_discarded) return;
		if (!frm?.is_dirty?.()) return;
		clearTimeout(frm.__retail_local_draft_timer);
		frm.__retail_local_draft_timer = setTimeout(() => requestIdleSave(frm), getSaveDelayMs(frm.doctype));
	}

	function setupAutoSaveLoop(frm) {
		clearInterval(frm.__retail_local_draft_interval);
		frm.__retail_local_draft_interval = setInterval(() => {
			if (window.cur_frm !== frm) {
				clearInterval(frm.__retail_local_draft_interval);
				return;
			}
			if (shouldTrack(frm) && frm.is_dirty?.() && canUseFullDocDraft(frm)) requestIdleSave(frm);
		}, CRITICAL_SAVE_DELAY_MS);
	}

	function requestIdleSave(frm) {
		if (frm.__retail_local_draft_saving) return;
		const run = () => saveDraft(frm);
		if (window.requestIdleCallback) {
			requestIdleCallback(run, { timeout: 10000 });
		} else {
			setTimeout(run, 500);
		}
	}

	async function offerRecovery(frm) {
		const key = getDraftKey(frm);
		if (!key || frm.__retail_recovery_checked) return;
		frm.__retail_recovery_checked = true;

		const draft = await getDraft(key);
		if (!draft || !draft.doc || draft.saved_docname !== getDocName(frm)) return;
		if (isExpiredDraft(draft)) {
			await deleteDraftByKey(key);
			return;
		}
		if (frm.is_dirty?.() && !isLocalDoc(frm)) return;

		frappe.confirm(
			__("Recover unsaved local draft from {0}?", [frappe.datetime.str_to_user(draft.updated_at_iso)]),
			() => restoreDraft(frm, draft),
			() => discardDraft(frm, key)
		);
	}

	async function saveDraft(frm) {
		if (frm?.__retail_local_draft_discarded) return;
		if (!frm?.doc || !frm.is_dirty?.()) return;
		if (!canUseFullDocDraft(frm)) {
			scheduleDraftSave(frm);
			return;
		}
		const key = getDraftKey(frm);
		if (!key) return;

		frm.__retail_local_draft_saving = true;
		let serialized;
		try {
			serialized = serializeDoc(frm);
		} finally {
			frm.__retail_local_draft_saving = false;
		}
		if (!serialized) return;

		const now = Date.now();
		const expiry_ms = getExpiryMs(frm.doctype);
		await putDraft({
			key,
			user: frappe.session.user,
			doctype: frm.doctype,
			docname: getDocName(frm),
			saved_docname: getDocName(frm),
			updated_at: now,
			expires_at: now + expiry_ms,
			expiry_hours: Math.round(expiry_ms / (60 * 60 * 1000)),
			updated_at_iso: new Date(now).toISOString(),
			doc: serialized.doc,
			bytes: serialized.bytes,
		});
	}

	function isExpiredDraft(draft) {
		const now = Date.now();
		if (draft.expires_at) return now > draft.expires_at;
		return now - draft.updated_at > getExpiryMs(draft.doctype);
	}

	function restoreDraft(frm, draft) {
		frm.__retail_local_draft_discarded = false;
		frm.doc.__unsaved_recovered_prompt = true;
		if (isLocalDoc(frm)) {
			restoreLocalDraft(frm, draft.doc);
		} else {
			frappe.model.sync(draft.doc);
			frm.doc = locals[frm.doctype]?.[draft.doc.name] || draft.doc;
		}
		frm.refresh();
		frm.dirty();
		frappe.show_alert({ message: __("Local draft recovered"), indicator: "green" });
		setTimeout(() => {
			delete frm.doc.__unsaved_recovered_prompt;
			scheduleDraftSave(frm);
		}, 1000);
	}

	async function discardDraft(frm, key) {
		clearTimeout(frm?.__retail_local_draft_timer);
		frm.__retail_local_draft_discarded = true;
		await deleteDraftByKey(key);
		frappe.show_alert({ message: __("Local draft discarded"), indicator: "orange" });
	}

	function restoreLocalDraft(frm, draftDoc) {
		const metaFields = frm.meta?.fields || [];
		const tableFields = new Set(metaFields.filter((df) => df.fieldtype === "Table").map((df) => df.fieldname));
		const fieldnames = new Set(metaFields.map((df) => df.fieldname));
		const skippedFields = new Set(["doctype", "name", "owner", "creation", "modified", "modified_by", "docstatus", "idx"]);
		let restoredFields = 0;
		let restoredRows = 0;

		for (const [fieldname, value] of Object.entries(draftDoc || {})) {
			if (skippedFields.has(fieldname) || tableFields.has(fieldname) || !fieldnames.has(fieldname)) continue;
			frm.doc[fieldname] = cloneValue(value);
			restoredFields += 1;
		}

		tableFields.forEach((fieldname) => {
			if (!Array.isArray(draftDoc?.[fieldname])) return;
			frm.clear_table(fieldname);
			draftDoc[fieldname].forEach((sourceRow) => {
				const row = frm.add_child(fieldname);
				Object.entries(sourceRow || {}).forEach(([key, value]) => {
					if (skippedFields.has(key) || ["parent", "parenttype", "parentfield"].includes(key)) return;
					row[key] = cloneValue(value);
				});
				restoredRows += 1;
			});
			frm.refresh_field(fieldname);
		});

		frm.refresh_fields();
		console.info("retail_local_draft_recovery: restored local draft", {
			doctype: frm.doctype,
			fields: restoredFields,
			rows: restoredRows,
		});
	}

	function cloneValue(value) {
		if (value == null || typeof value !== "object") return value;
		return JSON.parse(JSON.stringify(value));
	}

	function serializeDoc(frm) {
		const row_count = getChildRowCount(frm.doc);
		if (!isCriticalDoctype(frm.doctype) && row_count > MAX_SMALL_FORM_ROWS) {
			console.warn("retail_local_draft_recovery: skipped large small-form draft", frm.doctype);
			return null;
		}
		if (row_count > MAX_FULL_DOC_ROWS) {
			console.warn("retail_local_draft_recovery: skipped large full-document draft", frm.doctype, row_count);
			return null;
		}
		const json = JSON.stringify(frm.doc, (key, value) => {
			if (key.startsWith("__")) return undefined;
			if (typeof value === "function") return undefined;
			return value;
		});
		const bytes = new Blob([json]).size;
		if (bytes > MAX_DRAFT_BYTES) {
			console.warn("retail_local_draft_recovery: skipped oversized draft", frm.doctype, bytes);
			return null;
		}
		return { doc: JSON.parse(json), bytes };
	}

	function getChildRowCount(doc) {
		return Object.values(doc || {}).reduce((total, value) => {
			return total + (Array.isArray(value) ? value.length : 0);
		}, 0);
	}

	function canUseFullDocDraft(frm) {
		return getChildRowCount(frm?.doc) <= MAX_FULL_DOC_ROWS;
	}

	function getDraftKey(frm) {
		if (!frm?.doctype || !frm?.doc) return null;
		const company = frm.doc.company || frappe.defaults.get_default("company") || "";
		return [frappe.session.user, company, frm.doctype, getDocName(frm)].join("::");
	}

	function getDocName(frm) {
		if (!frm?.doc) return "";
		if (isLocalDoc(frm)) return "__new__";
		if (!frm.doc.__islocal && frm.doc.name) return frm.doc.name;
		return frm.doc.name || "new";
	}

	function isLocalDoc(frm) {
		return !!frm?.doc?.__islocal || String(frm?.doc?.name || "").startsWith("new-");
	}

	async function deleteDraft(frm) {
		clearTimeout(frm?.__retail_local_draft_timer);
		const key = getDraftKey(frm);
		if (key) await deleteDraftByKey(key);
	}

	function openDb() {
		if (window.__retail_local_draft_db) return window.__retail_local_draft_db;
		window.__retail_local_draft_db = new Promise((resolve, reject) => {
			const request = indexedDB.open(DB_NAME, DB_VERSION);
			request.onupgradeneeded = () => {
				const db = request.result;
				if (!db.objectStoreNames.contains(STORE_NAME)) {
					const store = db.createObjectStore(STORE_NAME, { keyPath: "key" });
					store.createIndex("updated_at", "updated_at", { unique: false });
				}
			};
			request.onsuccess = () => resolve(request.result);
			request.onerror = () => reject(request.error);
		});
		return window.__retail_local_draft_db;
	}

	async function putDraft(draft) {
		const db = await openDb();
		return txRequest(db, "readwrite", (store) => store.put(draft));
	}

	async function getDraft(key) {
		const db = await openDb();
		return txRequest(db, "readonly", (store) => store.get(key));
	}

	async function deleteDraftByKey(key) {
		const db = await openDb();
		return txRequest(db, "readwrite", (store) => store.delete(key));
	}

	async function cleanupOldDrafts() {
		const db = await openDb();
		return new Promise((resolve, reject) => {
			const tx = db.transaction(STORE_NAME, "readwrite");
			const request = tx.objectStore(STORE_NAME).openCursor();
			request.onsuccess = () => {
				const cursor = request.result;
				if (!cursor) return;
				if (isExpiredDraft(cursor.value)) {
					cursor.delete();
				}
				cursor.continue();
			};
			tx.oncomplete = () => resolve();
			tx.onerror = () => reject(tx.error);
			tx.onabort = () => reject(tx.error);
		});
	}

	function exposeDebugTools() {
		window.retailLocalDraftRecovery = {
			async current() {
				const frm = window.cur_frm;
				if (!frm) return null;
				const key = getDraftKey(frm);
				return {
					key,
					tracked: shouldTrack(frm),
					dirty: !!frm.is_dirty?.(),
					delay_ms: getSaveDelayMs(frm.doctype),
					draft: key ? await getDraft(key) : null,
				};
			},
			async saveNow() {
				const frm = window.cur_frm;
				if (!shouldTrack(frm)) return false;
				await saveDraft(frm);
				return true;
			},
		};
	}

	function txRequest(db, mode, callback) {
		return new Promise((resolve, reject) => {
			const tx = db.transaction(STORE_NAME, mode);
			const store = tx.objectStore(STORE_NAME);
			const request = callback(store);
			let result;
			request.onsuccess = () => {
				result = request.result;
			};
			tx.oncomplete = () => resolve(result);
			tx.onerror = () => reject(tx.error);
			tx.onabort = () => reject(tx.error);
		});
	}

	boot();
})();
