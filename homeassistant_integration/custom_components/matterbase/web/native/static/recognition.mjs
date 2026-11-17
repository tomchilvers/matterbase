// Recognition fills gaps. User edits, including deliberate blanks, always win.
export function mergeRecognition(target, suggestion) {
  let changed = false;
  for (const field of ['brand','product','color','icon']) {
    if (suggestion[field] && (!target[field] || target.overwrite_id) && !target[`${field}Edited`] && target[field]!==suggestion[field]) {
      target[field] = suggestion[field];
      changed = true;
      const source = ['brand','product'].includes(field) ? 'identity_source' : 'appearance_source';
      target[source] = suggestion[source];
    }
  }
  return changed;
}

export function useKnownProduct(code, devices) {
  if (code.vendor_id == null || code.product_id == null) return code;
  const matches = devices.filter(d => d.vendor_id === code.vendor_id && d.product_id === code.product_id);
  const result = {...code};
  for (const field of ['brand','product']) {
    const values = [...new Set(matches.map(d => d[field]?.trim()).filter(Boolean))];
    if (!result[field] && values.length === 1) {
      result[field] = values[0];
      result.identity_source = 'saved';
    }
  }
  return result;
}
