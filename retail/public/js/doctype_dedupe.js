// Share concurrent asynchronous metadata loads; retain native sync/callback behavior.
(() => {
 const original = frappe.model.with_doctype;
 if (original.retail_dedupe) return;
 const pending = new Map();
 function with_doctype(doctype, callback, async) {
  if (async === false || locals.DocType[doctype]) return original.apply(this, arguments);
  if (!pending.has(doctype)) {
   const request = Promise.resolve().then(() => original.call(this, doctype, null, async));
   const shared = request.finally(() => {
    if (pending.get(doctype) === shared) pending.delete(doctype);
   });
   pending.set(doctype, shared);
  }
  return pending.get(doctype).then(response => {
   callback && callback(response);
   return response;
  });
 }
 with_doctype.retail_dedupe = true;
 frappe.model.with_doctype = with_doctype;
})();
