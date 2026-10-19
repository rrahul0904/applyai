/**
 * Candidate-controlled, local-only field mapping foundation.
 * No DOM access, storage, network, auto-filling or form submissions.
 * A separate permission-gated scanner and review UI are required.
 */
const BLOCKED_TYPES = new Set(['password', 'hidden']);
const SENSITIVE_RE = /(?:work\s*authoriz|sponsor|visa|citizenship|immigrat|gender|pronouns?|race|ethnic|veteran|disabilit|birth\s*date|date\s*of\s*birth|dob\b|ssn\b|social\s*security|national\s*id|salary\s*expect|compensation\s*expect|criminal|background\s*check|eeo\b)/i;
const RULES = [
  ['email', /\b(e[ -]?mail|email address)\b/i],
  ['phone', /\b(phone|telephone|mobile number|contact number|tel)\b/i],
  ['linkedin', /\blinked\s?in\b/i],
  ['website', /\b(portfolio|personal website|website|github profile)\b/i],
  ['firstName', /\b(first name|given name|forename)\b/i],
  ['lastName', /\b(last name|family name|surname)\b/i],
  ['fullName', /\b(full name|your name|applicant name)\b/i],
  ['addressLine1', /\b(street address|address line 1|address1)\b/i],
  ['postalCode', /\b(zip code|postal code|postcode|zip)\b/i],
  ['city', /\b(city|town)\b/i],
  ['region', /\b(state|province|region)\b/i],
  ['country', /\bcountry\b/i]
];
const AUTO_COMPLETE = {
  email: 'email', tel: 'phone', 'given-name': 'firstName',
  'family-name': 'lastName', name: 'fullName',
  'address-line1': 'addressLine1', 'postal-code': 'postalCode',
  'address-level2': 'city', 'address-level1': 'region',
  country: 'country', 'country-name': 'country', url: 'website'
};

/** @returns {{kind:'blocked'|'manual'|'suggest', field?:string, reason:string}} */
export function classifyField(descriptor = {}) {
  const type = String(descriptor.type ?? '').trim().toLowerCase();
  if (BLOCKED_TYPES.has(type)) return { kind: 'blocked', reason: 'Blocked input type: ' + type };
  if (type === 'file') return { kind: 'manual', reason: 'Candidate must choose and upload files' };
  const evidence = [descriptor.label, descriptor.ariaLabel, descriptor.placeholder, descriptor.name, descriptor.id]
    .map((v) => String(v ?? '')).filter(Boolean).join(' ');
  const normalized = evidence.replace(/[_-]/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2');
  const autocomplete = String(descriptor.autocomplete ?? '').toLowerCase().trim();
  if (SENSITIVE_RE.test(normalized) || /(?:cc-|one-time-code|bday)/.test(autocomplete)) {
    return { kind: 'manual', reason: 'Sensitive or eligibility question needs a candidate answer' };
  }
  if (type === 'checkbox' || type === 'radio' || type === 'submit' || type === 'button') {
    return { kind: 'manual', reason: 'Manual field type: ' + type };
  }
  const standardToken = autocomplete.split(/\s+/).find((x) => AUTO_COMPLETE[x]);
  if (standardToken) return { kind: 'suggest', field: AUTO_COMPLETE[standardToken], reason: 'Standard autocomplete attribute' };
  const matching = RULES.filter(([, re]) => re.test(normalized));
  if (matching.length !== 1) return { kind: 'manual', reason: matching.length ? 'Ambiguous field' : 'Unrecognized field' };
  return { kind: 'suggest', field: matching[0][0], reason: 'Explicit form label or attribute' };
}

/** A proposed value is not a form write; every suggestion needs UI approval. */
export function proposeValue(descriptor, profile = {}) {
  const match = classifyField(descriptor);
  if (match.kind !== 'suggest') return { status: match.kind, reason: match.reason };
  const value = profile[match.field];
  if (typeof value !== 'string' || !value.trim()) return { status: 'manual', reason: 'Candidate profile has no verified value' };
  return { status: 'candidate_review_required', field: match.field, value, reason: match.reason };
}
