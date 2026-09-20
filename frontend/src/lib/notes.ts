import { useSyncExternalStore } from "react";

export interface EventNote {
  id: string;
  text: string;
}

// Notes are kept in localStorage so they survive refreshes until removed by
// hand. There is no notes API yet; swap load/save for a real call when one exists.
const STORAGE_KEY = "elderlink.notes.v1";
const EMPTY: EventNote[] = [];
const listeners = new Set<() => void>();

function load(): Map<string, EventNote[]> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return new Map(Object.entries(JSON.parse(raw) as Record<string, EventNote[]>));
  } catch {
    // Storage blocked or corrupt: start empty rather than break the panel.
  }
  return new Map();
}

const notes = load();

function commit() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(Object.fromEntries(notes)));
  } catch {
    // Still works for this session if storage is unavailable.
  }
  listeners.forEach((l) => l());
}

export function addNote(eventId: string, text: string) {
  const note = { id: crypto.randomUUID(), text };
  notes.set(eventId, [...(notes.get(eventId) ?? EMPTY), note]);
  commit();
}

export function removeNote(eventId: string, noteId: string) {
  const next = (notes.get(eventId) ?? EMPTY).filter((n) => n.id !== noteId);
  if (next.length) notes.set(eventId, next);
  else notes.delete(eventId);
  commit();
}

export function useNotes(eventId: string): EventNote[] {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => notes.get(eventId) ?? EMPTY,
  );
}
