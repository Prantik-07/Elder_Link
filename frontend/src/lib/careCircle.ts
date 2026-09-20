import { useSyncExternalStore } from "react";
import { CAREGIVERS, type Caregiver } from "../data/caregivers";

// The Care Circle has no backend yet, so members the caregiver adds and any
// emails they fill in live in localStorage. Built-in caregivers stay in code;
// only their email is stored (by id). Swap load/save for an API when one exists.
const STORAGE_KEY = "elderlink.careCircle.v1";

interface Stored {
  added: Caregiver[];
  emails: Record<string, string>;
}

function load(): Stored {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<Stored>;
      return { added: parsed.added ?? [], emails: parsed.emails ?? {} };
    }
  } catch {
    // Blocked or corrupt storage: start from the built-in circle.
  }
  return { added: [], emails: {} };
}

let stored = load();
const listeners = new Set<() => void>();

function compute(): Caregiver[] {
  return [...CAREGIVERS, ...stored.added].map((c) =>
    stored.emails[c.id] ? { ...c, email: stored.emails[c.id] } : c,
  );
}

// useSyncExternalStore needs a referentially stable snapshot between changes.
let snapshot = compute();

function commit() {
  snapshot = compute();
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(stored));
  } catch {
    // Still works for this session if storage is unavailable.
  }
  listeners.forEach((l) => l());
}

export function getCareCircle(): Caregiver[] {
  return snapshot;
}

export function addMember(member: Omit<Caregiver, "id">) {
  const id = `${member.name.toLowerCase().replace(/\s+/g, "-")}-${crypto.randomUUID().slice(0, 6)}`;
  stored = {
    added: [...stored.added, { ...member, id, email: undefined }],
    emails: member.email ? { ...stored.emails, [id]: member.email } : stored.emails,
  };
  commit();
}

export function setMemberEmail(id: string, email: string) {
  const emails = { ...stored.emails };
  if (email) emails[id] = email;
  else delete emails[id];
  stored = { ...stored, emails };
  commit();
}

export function useCareCircle(): Caregiver[] {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => snapshot,
  );
}
