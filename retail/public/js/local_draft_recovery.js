(function () {
	if (window.__retail_local_draft_recovery_booted) return;
	window.__retail_local_draft_recovery_booted = true;

	const DB_NAME = "retail_local_draft_recovery";
	const DB_VERSION = 1;
	const STORE_NAME = "drafts";
	const SESSION_ID_KEY = "retail_local_draft_recovery_session_id";
	const EMERGENCY_DRAFT_PREFIX = "retail_local_draft_recovery_emergency::";
	const CRITICAL_EXPIRY_MS = 48 * 60 * 60 * 1000;
	const SMALL_FORM_EXPIRY_MS = 12 * 60 * 60 * 1000;
	const CRITICAL_SAVE_DELAY_MS = 30000;
	const SMALL_FORM_SAVE_DELAY_MS = 5000;
	const MAX_DRAFT_BYTES = 8 * 1024 * 1024;
	const MAX_SMALL_FORM_ROWS = 250;
	const MAX_FULL_DOC_ROWS = 500;
	const LOCAL_DRAFT_PROMPT_IGNORE_FIELDS = new Set([
		"doctype",
		"name",
		"owner",
		"creation",
		"modified",
		"modified_by",
		"docstatus",
		"idx",
		"__islocal",
		"naming_series",
		"company",
		"currency",
		"conversion_rate",
		"price_list_currency",
		"plc_conversion_rate",
		"posting_date",
		"posting_time",
		"set_posting_time",
		"transaction_date",
		"schedule_date",
		"delivery_date",
		"due_date",
		"payment_due_date",
		"status",
	]);
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
	let navigation_guard_installed = false;
	let navigation_bypass = false;
	let navigation_dialog_open = false;
	let dirty_form_state = null;

	function boot() {
		if (!window.frappe?.ui?.form) {
			setTimeout(boot, 150);
			return;
		}
		registerHandlers();
		setupNavigationGuard();
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
					updateCleanBaseline(frm);
					bindFormDirtyTracker(frm);
					if (isCriticalDoctype(frm.doctype) && canUseFullDocDraft(frm)) {
						setupAutoSaveLoop(frm);
					}
					scheduleCleanDirtyStateChecks(frm);
					scheduleDraftSave(frm);
				},
				after_save(frm) {
					deleteDraft(frm);
					updateCleanBaseline(frm);
					clearDirtyFormState(frm);
					scheduleCleanDirtyStateChecks(frm);
				},
				on_submit(frm) {
					deleteDraft(frm);
					updateCleanBaseline(frm);
					clearDirtyFormState(frm);
				},
				before_discard(frm) {
					deleteDraft(frm);
					updateCleanBaseline(frm);
					clearDirtyFormState(frm);
				},
			});
		});

		$(document).on("form-dirty", () => {
			const frm = window.cur_frm;
			if (shouldTrack(frm)) {
				handleTrackedFormDirty(frm);
			}
		});

		document.addEventListener("visibilitychange", () => {
			if (document.visibilityState !== "hidden") return;
			const frm = window.cur_frm;
			if (shouldTrack(frm) && frm.is_dirty?.() && canUseFullDocDraft(frm)) {
				saveEmergencyDraft(frm);
				saveDraft(frm);
			}
		});

		window.addEventListener("pagehide", () => {
			const frm = window.cur_frm;
			if (shouldTrack(frm) && frm.is_dirty?.() && canUseFullDocDraft(frm)) {
				saveEmergencyDraft(frm);
			}
		});
	}

	function setupNavigationGuard() {
		if (navigation_guard_installed || !frappe.router?.set_route || !frappe.router?.route) return;
		navigation_guard_installed = true;

		const original_set_route = frappe.router.set_route.bind(frappe.router);
		const original_route = frappe.router.route.bind(frappe.router);
		const original_history_back = window.history.back.bind(window.history);
		const original_history_go = window.history.go.bind(window.history);

		frappe.router.set_route = function () {
			if (navigation_bypass) return original_set_route.apply(frappe.router, arguments);
			const frm = getDirtyNavigationForm();
			if (!hasUnsavedNavigationChanges(frm)) {
				return original_set_route.apply(frappe.router, arguments);
			}

			const args = Array.from(arguments);
			showUnsavedNavigationDialog(frm, () => {
				navigation_bypass = true;
				original_set_route.apply(frappe.router, args).finally(() => {
					navigation_bypass = false;
				});
			});
			return Promise.resolve(false);
		};

		frappe.router.route = async function () {
			if (navigation_bypass) return original_route();
			const frm = getDirtyNavigationForm();
			const next_sub_path = frappe.router.get_sub_path();
			const current_sub_path = frappe.router.current_sub_path;
			if (
				!current_sub_path ||
				next_sub_path === current_sub_path ||
				!hasUnsavedNavigationChanges(frm)
			) {
				return original_route();
			}

			showUnsavedNavigationDialog(
				frm,
				() => {
					navigation_bypass = true;
					original_route().finally(() => {
						navigation_bypass = false;
					});
				},
				() => restoreFormRoute(frm)
			);
			return false;
		};

		window.addEventListener(
			"beforeunload",
			(event) => {
				const frm = getDirtyNavigationForm();
				if (!hasUnsavedNavigationChanges(frm)) return;
				saveEmergencyDraft(frm);
				if (canUseFullDocDraft(frm)) saveDraft(frm);
				event.preventDefault();
				event.returnValue = "";
				return "";
			},
			{ capture: true }
		);

		window.history.back = function () {
			if (navigation_bypass) return original_history_back();
			const frm = getDirtyNavigationForm();
			if (!hasUnsavedNavigationChanges(frm)) return original_history_back();

			showUnsavedNavigationDialog(
				frm,
				() => {
					navigation_bypass = true;
					original_history_back();
					setTimeout(() => {
						navigation_bypass = false;
					}, 500);
				},
				() => restoreFormRoute(frm)
			);
		};

		window.history.go = function (delta) {
			if (navigation_bypass || delta >= 0) return original_history_go(delta);
			const frm = getDirtyNavigationForm();
			if (!hasUnsavedNavigationChanges(frm)) return original_history_go(delta);

			showUnsavedNavigationDialog(
				frm,
				() => {
					navigation_bypass = true;
					original_history_go(delta);
					setTimeout(() => {
						navigation_bypass = false;
					}, 500);
				},
				() => restoreFormRoute(frm)
			);
		};
	}

	function hasUnsavedNavigationChanges(frm) {
		return !!(
			shouldTrack(frm) &&
			frm.is_dirty?.() &&
			!frm.__retail_local_draft_discarded
		);
	}

	function getDirtyNavigationForm() {
		const current_sub_path = frappe.router?.current_sub_path;
		const frm = window.cur_frm;
		if (hasUnsavedNavigationChanges(frm) && isCurrentFormRoute(frm, current_sub_path)) {
			return frm;
		}
		if (
			dirty_form_state?.frm &&
			dirty_form_state.sub_path === current_sub_path &&
			hasUnsavedNavigationChanges(dirty_form_state.frm)
		) {
			return dirty_form_state.frm;
		}
		return null;
	}

	function isCurrentFormRoute(frm, current_sub_path = frappe.router?.current_sub_path) {
		const form_sub_path = getFormSubPath(frm);
		return !!form_sub_path && current_sub_path === form_sub_path;
	}

	function getFormSubPath(frm) {
		const docname = frm?.doc?.name || frm?.docname;
		if (!frm?.doctype || !docname || !frappe.router?.make_url) return null;
		return frappe.router.get_sub_path(frappe.router.make_url(["Form", frm.doctype, docname]));
	}

	function bindFormDirtyTracker(frm) {
		if (!frm?.$wrapper || frm.__retail_local_draft_dirty_tracker_bound) return;
		frm.__retail_local_draft_dirty_tracker_bound = true;
		frm.$wrapper.on("dirty.retailLocalDraftRecovery", () => handleTrackedFormDirty(frm));
	}

	function handleTrackedFormDirty(frm) {
		if (!shouldTrack(frm)) return;
		dirty_form_state = {
			frm,
			sub_path: getFormSubPath(frm),
			updated_at: Date.now(),
		};
		saveEmergencyDraft(frm);
		scheduleDraftSave(frm);
	}

	function clearDirtyFormState(frm) {
		if (dirty_form_state?.frm === frm) {
			dirty_form_state = null;
		}
	}

	function showUnsavedNavigationDialog(frm, onDiscard, onContinue) {
		if (navigation_dialog_open) return;
		navigation_dialog_open = true;
		let dialog_action_taken = false;

		const dialog = new frappe.ui.Dialog({
			title: __("Unsaved Changes"),
			fields: [
				{
					fieldtype: "HTML",
					fieldname: "message",
					options: `<div class="frappe-confirm-message">${__(
						"This form has unsaved changes. Discard them and leave this form?"
					)}</div>`,
				},
			],
			primary_action_label: __("Discard Changes"),
			primary_action: async () => {
				dialog_action_taken = true;
				await discardUnsavedForNavigation(frm);
				dialog.hide();
				onDiscard?.();
			},
			secondary_action_label: __("Continue Editing"),
			secondary_action: () => {
				dialog_action_taken = true;
				dialog.hide();
				onContinue?.();
			},
		});

		dialog.$wrapper.find(".btn-primary").removeClass("btn-primary").addClass("btn-danger");
		dialog.onhide = () => {
			navigation_dialog_open = false;
			if (!dialog_action_taken) {
				onContinue?.();
			}
		};
		dialog.show();
	}

	async function discardUnsavedForNavigation(frm) {
		clearTimeout(frm?.__retail_local_draft_timer);
		frm.__retail_local_draft_discarded = true;
		await deleteDraft(frm);
		clearDirtyFormState(frm);
		if (frm?.doc) frm.doc.__unsaved = 0;
		if (frm?.beforeUnloadListener) {
			removeEventListener("beforeunload", frm.beforeUnloadListener, { capture: true });
		}
	}

	function restoreFormRoute(frm) {
		const form_sub_path = getFormSubPath(frm);
		if (!form_sub_path) return;
		navigation_bypass = true;
		frappe.router.set_route(form_sub_path).finally(() => {
			navigation_bypass = false;
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
		if (!hasChangedFromCleanBaseline(frm)) return;
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
			if (shouldTrack(frm) && frm.is_dirty?.() && hasChangedFromCleanBaseline(frm) && canUseFullDocDraft(frm)) {
				requestIdleSave(frm);
			}
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

		const indexed_draft = await getDraft(key);
		const emergency_draft = getEmergencyDraft(key);
		const draft = indexed_draft || emergency_draft;
		if (!draft || !draft.doc || draft.saved_docname !== getDocName(frm)) return;
		if (draft.user && draft.user !== frappe.session.user) {
			await deleteDraftByKey(key);
			return;
		}
		if (isExpiredDraft(draft)) {
			await deleteDraftByKey(key);
			return;
		}
		if (isDraftOlderThanCurrentDoc(frm, draft)) {
			await deleteDraftByKey(key);
			return;
		}
		if (frm.is_dirty?.() && !isLocalDoc(frm)) return;
		if (isLocalDoc(frm) && !hasRecoverableLocalDraftContent(frm, draft.doc)) {
			await deleteDraftByKey(key);
			return;
		}
		if (!hasRecoverableDraftDifference(frm, draft.doc)) {
			await deleteDraftByKey(key);
			deleteEmergencyDraftByKey(key);
			return;
		}
		if (draft.prompted_at) return;

		await markDraftPrompted(key, draft, {
			has_indexed_draft: !!indexed_draft,
			has_emergency_draft: !!emergency_draft,
		});
		frm.__retail_local_draft_prompted = true;

		frappe.confirm(
			__("Recover unsaved local draft from {0}?", [frappe.datetime.str_to_user(draft.updated_at_iso)]),
			() => restoreDraft(frm, draft),
			() => discardDraft(frm, key)
		);
	}

	async function saveDraft(frm) {
		if (frm?.__retail_local_draft_discarded) return;
		if (!frm?.doc || !frm.is_dirty?.()) return;
		if (!hasChangedFromCleanBaseline(frm)) return;
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
		if (isLocalDoc(frm) && !hasRecoverableLocalDraftContent(frm, serialized.doc)) {
			await deleteDraftByKey(key);
			return;
		}

		const now = Date.now();
		const expiry_ms = getExpiryMs(frm.doctype);
		const prompted_at = frm.__retail_local_draft_prompted ? now : null;
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
			browser_session_id: getBrowserSessionId(),
			doc: serialized.doc,
			bytes: serialized.bytes,
			prompted_at,
			prompted_at_iso: prompted_at ? new Date(prompted_at).toISOString() : null,
		});
		deleteEmergencyDraftByKey(key);
	}

	function saveEmergencyDraft(frm) {
		if (frm?.__retail_local_draft_discarded) return;
		if (!frm?.doc || !frm.is_dirty?.() || !hasChangedFromCleanBaseline(frm)) return;
		const key = getDraftKey(frm);
		if (!key) return;

		const serialized = serializeDoc(frm);
		if (!serialized) return;
		if (isLocalDoc(frm) && !hasRecoverableLocalDraftContent(frm, serialized.doc)) {
			deleteEmergencyDraftByKey(key);
			return;
		}

		const now = Date.now();
		const expiry_ms = getExpiryMs(frm.doctype);
		const prompted_at = frm.__retail_local_draft_prompted ? now : null;
		try {
			localStorage.setItem(
				getEmergencyDraftKey(key),
				JSON.stringify({
					key,
					user: frappe.session.user,
					doctype: frm.doctype,
					docname: getDocName(frm),
					saved_docname: getDocName(frm),
					updated_at: now,
					expires_at: now + expiry_ms,
					expiry_hours: Math.round(expiry_ms / (60 * 60 * 1000)),
					updated_at_iso: new Date(now).toISOString(),
					browser_session_id: getBrowserSessionId(),
					doc: serialized.doc,
					bytes: serialized.bytes,
					emergency: true,
					prompted_at,
					prompted_at_iso: prompted_at ? new Date(prompted_at).toISOString() : null,
				})
			);
		} catch (error) {
			console.warn("retail_local_draft_recovery: emergency draft save failed", error);
		}
	}

	function getEmergencyDraft(key) {
		try {
			const value = localStorage.getItem(getEmergencyDraftKey(key));
			return value ? JSON.parse(value) : null;
		} catch {
			return null;
		}
	}

	async function markDraftPrompted(key, draft, options = {}) {
		const now = Date.now();
		const prompted_draft = {
			...draft,
			prompted_at: now,
			prompted_at_iso: new Date(now).toISOString(),
		};

		if (options.has_indexed_draft) {
			await putDraft(prompted_draft);
		}
		if (options.has_emergency_draft) {
			try {
				localStorage.setItem(getEmergencyDraftKey(key), JSON.stringify(prompted_draft));
			} catch {
				// ignore one-shot marker failures
			}
		}
	}

	function isExpiredDraft(draft) {
		const now = Date.now();
		if (draft.expires_at) return now > draft.expires_at;
		return now - draft.updated_at > getExpiryMs(draft.doctype);
	}

	function isDraftOlderThanCurrentDoc(frm, draft) {
		if (isLocalDoc(frm) || !frm.doc?.modified || !draft.updated_at) return false;
		const modified = frappe.datetime.str_to_obj(frm.doc.modified);
		if (!modified) return false;
		return draft.updated_at <= modified.getTime();
	}

	function hasRecoverableLocalDraftContent(frm, draftDoc) {
		const metaFields = frm.meta?.fields || [];
		const tableFields = new Set(metaFields.filter((df) => df.fieldtype === "Table").map((df) => df.fieldname));
		const fieldnames = new Set(metaFields.map((df) => df.fieldname));

		for (const [fieldname, value] of Object.entries(draftDoc || {})) {
			if (tableFields.has(fieldname)) {
				if (hasRecoverableTableRows(value)) return true;
				continue;
			}
			if (!fieldnames.has(fieldname) || LOCAL_DRAFT_PROMPT_IGNORE_FIELDS.has(fieldname)) continue;
			if (hasMeaningfulValue(value)) return true;
		}

		return false;
	}

	function hasRecoverableTableRows(rows) {
		if (!Array.isArray(rows)) return false;
		return rows.some((row) => {
			return Object.entries(row || {}).some(([fieldname, value]) => {
				if (
					LOCAL_DRAFT_PROMPT_IGNORE_FIELDS.has(fieldname) ||
					["parent", "parenttype", "parentfield"].includes(fieldname)
				) {
					return false;
				}
				return hasMeaningfulValue(value);
			});
		});
	}

	function hasMeaningfulValue(value) {
		if (value == null || value === "" || value === 0 || value === false) return false;
		if (Array.isArray(value)) return value.length > 0;
		if (typeof value === "object") return Object.keys(value).length > 0;
		return true;
	}

	function restoreDraft(frm, draft) {
		frm.__retail_local_draft_discarded = false;
		frm.__retail_local_draft_prompted = true;
		frm.doc.__unsaved_recovered_prompt = true;
		restoreFormDraft(frm, draft.doc);
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
		deleteEmergencyDraftByKey(key);
		frappe.show_alert({ message: __("Local draft discarded"), indicator: "orange" });
	}

	function restoreFormDraft(frm, draftDoc) {
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

	function updateCleanBaseline(frm) {
		if (frm.is_dirty?.()) return;
		frm.__retail_local_draft_baseline = getRecoveryFingerprint(frm, frm.doc);
	}

	function scheduleCleanDirtyStateChecks(frm) {
		if (!shouldTrack(frm) || isLocalDoc(frm)) return;

		frm.__retail_local_draft_user_changed = false;
		bindUserChangeTracker(frm);

		[100, 500, 1200, 2500].forEach((delay) => {
			setTimeout(() => clearCleanDirtyState(frm), delay);
		});
	}

	function bindUserChangeTracker(frm) {
		if (!frm?.$wrapper || frm.__retail_local_draft_user_tracker_bound) return;

		frm.__retail_local_draft_user_tracker_bound = true;
		const markUserChanged = (event) => {
			if (!event.originalEvent?.isTrusted) return;
			frm.__retail_local_draft_user_changed = true;
			frm.__retail_local_draft_last_user_event_at = Date.now();
		};
		const markUserEdited = (event) => {
			markUserChanged(event);
			if (!event.originalEvent?.isTrusted || !shouldTrack(frm)) return;
			if (!frm.is_dirty?.()) {
				frm.dirty();
			}
			handleTrackedFormDirty(frm);
		};

		frm.$wrapper.on(
			"input.retailLocalDraftRecovery change.retailLocalDraftRecovery paste.retailLocalDraftRecovery cut.retailLocalDraftRecovery",
			":input, .control-input, .form-control, .awesomplete, [data-fieldname]",
			markUserEdited
		);
		frm.$wrapper.on(
			"pointerdown.retailLocalDraftRecovery click.retailLocalDraftRecovery",
			":input, .control-input, .grid-row, .form-control, .awesomplete, [data-fieldname]",
			markUserChanged
		);
	}

	function clearCleanDirtyState(frm) {
		if (!shouldTrack(frm) || !frm.is_dirty?.() || isLocalDoc(frm)) return;
		if (frm.__retail_local_draft_user_changed) return;

		const current_fingerprint = getRecoveryFingerprint(frm, frm.doc);
		if (!frm.__retail_local_draft_baseline) {
			frm.__retail_local_draft_baseline = current_fingerprint;
		}
		if (frm.__retail_local_draft_baseline !== current_fingerprint) return;

		clearTimeout(frm.__retail_local_draft_timer);
		frm.doc.__unsaved = 0;
		if (frm.beforeUnloadListener) {
			removeEventListener("beforeunload", frm.beforeUnloadListener, { capture: true });
		}
		frm.toolbar?.refresh?.();
	}

	function hasChangedFromCleanBaseline(frm) {
		if (!frm?.doc) return false;
		if (!frm.__retail_local_draft_baseline) {
			updateCleanBaseline(frm);
			return frm.is_dirty?.() && isLocalDoc(frm) && hasRecoverableLocalDraftContent(frm, frm.doc);
		}

		return frm.__retail_local_draft_baseline !== getRecoveryFingerprint(frm, frm.doc);
	}

	function hasRecoverableDraftDifference(frm, draftDoc) {
		return getRecoveryFingerprint(frm, frm.doc) !== getRecoveryFingerprint(frm, draftDoc);
	}

	function getRecoveryFingerprint(frm, doc) {
		return JSON.stringify(getRecoveryComparableDoc(frm, doc));
	}

	function getRecoveryComparableDoc(frm, doc) {
		const metaFields = frm.meta?.fields || [];
		const tableFields = new Set(metaFields.filter((df) => df.fieldtype === "Table").map((df) => df.fieldname));
		const fieldnames = new Set(metaFields.map((df) => df.fieldname));
		const comparable = {};

		metaFields.forEach((df) => {
			const fieldname = df.fieldname;
			if (!fieldname || !fieldnames.has(fieldname) || LOCAL_DRAFT_PROMPT_IGNORE_FIELDS.has(fieldname)) return;
			if (tableFields.has(fieldname)) {
				const rows = Array.isArray(doc?.[fieldname]) ? doc[fieldname] : [];
				const comparableRows = rows.map((row) => getComparableChildRow(row)).filter((row) => Object.keys(row).length);
				if (comparableRows.length) comparable[fieldname] = comparableRows;
				return;
			}

			const value = normalizeComparableValue(doc?.[fieldname]);
			if (hasMeaningfulValue(value)) comparable[fieldname] = value;
		});

		return comparable;
	}

	function getComparableChildRow(row) {
		const comparable = {};
		Object.entries(row || {}).forEach(([fieldname, value]) => {
			if (
				LOCAL_DRAFT_PROMPT_IGNORE_FIELDS.has(fieldname) ||
				["name", "parent", "parenttype", "parentfield", "idx"].includes(fieldname)
			) {
				return;
			}

			value = normalizeComparableValue(value);
			if (hasMeaningfulValue(value)) comparable[fieldname] = value;
		});
		return comparable;
	}

	function normalizeComparableValue(value) {
		if (value == null) return "";
		if (Array.isArray(value)) return value.map(normalizeComparableValue);
		if (typeof value === "object") {
			const normalized = {};
			Object.keys(value)
				.sort()
				.forEach((key) => {
					normalized[key] = normalizeComparableValue(value[key]);
				});
			return normalized;
		}
		return value;
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

	function getBrowserSessionId() {
		let session_id = sessionStorage.getItem(SESSION_ID_KEY);
		if (!session_id) {
			session_id = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
			sessionStorage.setItem(SESSION_ID_KEY, session_id);
		}
		return session_id;
	}

	async function deleteDraft(frm) {
		clearTimeout(frm?.__retail_local_draft_timer);
		const key = getDraftKey(frm);
		if (key) {
			await deleteDraftByKey(key);
			deleteEmergencyDraftByKey(key);
		}
	}

	function getEmergencyDraftKey(key) {
		return `${EMERGENCY_DRAFT_PREFIX}${key}`;
	}

	function deleteEmergencyDraftByKey(key) {
		try {
			localStorage.removeItem(getEmergencyDraftKey(key));
		} catch {
			// ignore cleanup failures
		}
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
