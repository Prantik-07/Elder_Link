import { useState } from "react";
import { Calendar, Check, CircleHelp, Loader2, MapPin, StickyNote, Trash2, User, X } from "lucide-react";
import type { CareEvent, CareEventStatus } from "../data/types";
import { CATEGORY_META } from "../lib/categoryMeta";
import { formatTimestamp } from "../lib/format";
import { addNote, removeNote, useNotes } from "../lib/notes";
import { StatusBadge } from "./StatusBadge";
import { AudioEvidencePlayer } from "./AudioEvidencePlayer";

const REASON_COPY: Record<CareEventStatus, string> = {
  verified: "This was reported in clear, confident language and has been confirmed.",
  needs_verification:
    "The caregiver used uncertain language, so this needs to be confirmed with the care recipient or another caregiver.",
  uncertain: "There isn't enough evidence yet to confirm or resolve this either way.",
};

export function EvidencePanel({
  event,
  onClose,
  onSetStatus,
}: {
  event: CareEvent;
  onClose?: () => void;
  onSetStatus: (status: CareEventStatus) => Promise<void>;
}) {
  const meta = CATEGORY_META[event.type];
  const Icon = meta.icon;
  const label = event.categoryLabel ?? meta.label;
  const reason = event.verificationReason ?? REASON_COPY[event.status];
  const notes = useNotes(event.id);
  const [noteOpen, setNoteOpen] = useState(false);
  const [draft, setDraft] = useState("");

  const saveNote = () => {
    const text = draft.trim();
    if (!text) return;
    addNote(event.id, text);
    setDraft("");
    setNoteOpen(false);
  };

  const [pendingStatus, setPendingStatus] = useState<CareEventStatus | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  const handleSetStatus = async (status: CareEventStatus) => {
    setPendingStatus(status);
    setSaveError(null);
    try {
      await onSetStatus(status);
    } catch (err) {
      // The write failed - the status shown above is still whatever the
      // backend last confirmed, never the attempted value, so this error
      // message is the only place the failure is visible. Never treat a
      // rejected save as if it succeeded.
      setSaveError(err instanceof Error ? err.message : "Couldn't save. Try again.");
    } finally {
      setPendingStatus(null);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-start justify-between gap-3 border-b px-6 py-[1.125rem]" style={{ borderColor: "var(--color-line)" }}>
        <span
          className="inline-flex items-center gap-2 text-[12px] font-semibold tracking-wide uppercase"
          style={{ color: meta.iconColor }}
        >
          <span
            className="flex h-7 w-7 items-center justify-center rounded-lg"
            style={{ backgroundColor: meta.iconBg }}
            aria-hidden="true"
          >
            <Icon size={14} strokeWidth={2} />
          </span>
          {label}
        </span>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            aria-label="Close event detail"
            className="rounded-full p-1.5 text-[var(--color-ink-muted)] hover:bg-[var(--color-ivory-soft)] hover:text-[var(--color-ink)]"
          >
            <X size={18} aria-hidden="true" />
          </button>
        )}
      </div>

      <div className="thin-scroll flex-1 overflow-y-auto px-6 py-6">
        <h2 className="font-display text-[24px] leading-[1.25] font-medium text-[var(--color-ink)]">
          {event.title}
        </h2>
        <p className="mt-1.5 text-[14px] leading-snug text-[var(--color-ink-muted)]">{event.summary}</p>

        <dl className="mt-3.5 flex flex-wrap gap-x-5 gap-y-1.5 text-[13px] text-[var(--color-ink-muted)]">
          <div className="flex items-center gap-1.5">
            <Calendar size={13} aria-hidden="true" />
            <dt className="sr-only">When</dt>
            <dd>{formatTimestamp(event.occurredAt)}</dd>
          </div>
          <div className="flex items-center gap-1.5">
            <User size={13} aria-hidden="true" />
            <dt className="sr-only">Reported by</dt>
            <dd>{event.reportedBy}</dd>
          </div>
          {event.location && (
            <div className="flex items-center gap-1.5">
              <MapPin size={13} aria-hidden="true" />
              <dt className="sr-only">Location</dt>
              <dd>{event.location}</dd>
            </div>
          )}
        </dl>

        <section className="mt-6">
          <h3 className="text-[13px] font-semibold text-[var(--color-ink)]">What happened?</h3>
          <p className="mt-1.5 text-[14px] leading-relaxed text-[var(--color-ink-soft)]">
            {event.whatHappened}
          </p>
        </section>

        {event.evidence && (
          <section className="mt-7">
            <h3 className="text-[13px] font-semibold text-[var(--color-ink)]">
              Evidence from voice note
            </h3>
            <div className="mt-2.5 space-y-3">
              <AudioEvidencePlayer
                segmentId={event.evidence.segmentId}
                durationSeconds={event.evidence.durationSeconds ?? 15}
              />
              <div>
                <span className="text-[12px] font-semibold tracking-wide text-[var(--color-ink-muted)] uppercase">
                  Transcript excerpt
                </span>
                <blockquote
                  className="mt-1.5 rounded-lg border-l-2 py-1 pl-3.5 text-[14px] leading-relaxed text-[var(--color-ink-soft)] italic"
                  style={{ borderColor: "var(--color-teal)" }}
                >
                  &ldquo;{event.evidence.transcript}&rdquo;
                </blockquote>
              </div>
            </div>
          </section>
        )}

        <section className="mt-7 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="rounded-xl border p-3.5" style={{ borderColor: "var(--color-line)" }}>
            <span className="text-[12px] font-semibold tracking-wide text-[var(--color-ink-muted)] uppercase">
              Verification status
            </span>
            <div className="mt-2">
              <StatusBadge status={event.status} />
            </div>
          </div>
          <div className="rounded-xl border p-3.5" style={{ borderColor: "var(--color-line)" }}>
            <span className="flex items-center gap-1.5 text-[12px] font-semibold tracking-wide text-[var(--color-ink-muted)] uppercase">
              <CircleHelp size={12} aria-hidden="true" />
              Why verification is required
            </span>
            <p className="mt-1.5 text-[13px] leading-snug text-[var(--color-ink-soft)]">{reason}</p>
          </div>
        </section>

        {(notes.length > 0 || noteOpen) && (
          <section className="mt-7">
            <h3 className="text-[13px] font-semibold text-[var(--color-ink)]">Notes</h3>
            <ul className="mt-2 space-y-2">
              {notes.map((n) => (
                <li
                  key={n.id}
                  className="flex items-start gap-2 rounded-lg border px-3 py-2 text-[13.5px] leading-snug text-[var(--color-ink-soft)]"
                  style={{ borderColor: "var(--color-line)", backgroundColor: "var(--color-ivory-soft)" }}
                >
                  <span className="min-w-0 flex-1 break-words whitespace-pre-wrap">{n.text}</span>
                  <button
                    type="button"
                    onClick={() => removeNote(event.id, n.id)}
                    aria-label="Delete note"
                    className="-my-1 -mr-1.5 shrink-0 rounded-full p-2 text-[var(--color-ink-muted)] transition-colors hover:text-[var(--color-concern)]"
                  >
                    <Trash2 size={14} aria-hidden="true" />
                  </button>
                </li>
              ))}
            </ul>
            {noteOpen && (
              <div className="mt-2.5">
                <textarea
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  autoFocus
                  rows={3}
                  aria-label="Note"
                  placeholder="Add a note for the next caregiver..."
                  className="w-full rounded-lg border bg-[var(--color-paper)] px-3 py-2 text-[14px]"
                  style={{ borderColor: "var(--color-line)" }}
                />
                <div className="mt-2 flex gap-2">
                  <button
                    type="button"
                    onClick={saveNote}
                    className="rounded-full px-4 py-2 text-[13px] font-semibold text-[var(--color-paper)]"
                    style={{ backgroundColor: "var(--color-teal)" }}
                  >
                    Save note
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setNoteOpen(false);
                      setDraft("");
                    }}
                    className="rounded-full border px-4 py-2 text-[13px] font-semibold text-[var(--color-ink-soft)]"
                    style={{ borderColor: "var(--color-line)" }}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </section>
        )}
      </div>

      <div
        className="flex flex-col gap-2 border-t px-6 py-[1.125rem] sm:flex-row sm:flex-wrap sm:items-center sm:gap-2.5"
        style={{ borderColor: "var(--color-line)", paddingBottom: "max(1.125rem, env(safe-area-inset-bottom))" }}
      >
        <button
          type="button"
          onClick={() => handleSetStatus("verified")}
          disabled={pendingStatus !== null}
          className="flex w-full items-center justify-center gap-1.5 rounded-full px-4 py-3 text-[14px] font-semibold text-[var(--color-paper)] transition-opacity hover:opacity-90 disabled:opacity-60 sm:w-auto sm:py-2 sm:text-[13px]"
          style={{ backgroundColor: "var(--color-teal)" }}
        >
          {pendingStatus === "verified" ? (
            <Loader2 size={14} className="animate-spin" aria-hidden="true" />
          ) : (
            <Check size={14} aria-hidden="true" />
          )}
          Mark as Verified
        </button>
        <button
          type="button"
          onClick={() => handleSetStatus("uncertain")}
          disabled={pendingStatus !== null}
          className="flex w-full items-center justify-center gap-1.5 rounded-full border px-4 py-3 text-[14px] font-semibold text-[var(--color-ink-soft)] transition-colors hover:text-[var(--color-ink)] disabled:opacity-60 sm:w-auto sm:py-2 sm:text-[13px]"
          style={{ borderColor: "var(--color-line)" }}
        >
          {pendingStatus === "uncertain" && <Loader2 size={14} className="animate-spin" aria-hidden="true" />}
          Keep Uncertain
        </button>
        {saveError && (
          <p className="w-full text-[12.5px] leading-snug text-[var(--color-concern)]" role="alert">
            {saveError}
          </p>
        )}
        <button
          type="button"
          onClick={() => setNoteOpen(true)}
          className="flex w-full items-center justify-center gap-1.5 rounded-full border px-4 py-3 text-[14px] font-semibold text-[var(--color-ink-soft)] transition-colors hover:text-[var(--color-ink)] sm:w-auto sm:py-2 sm:text-[13px]"
          style={{ borderColor: "var(--color-line)" }}
        >
          <StickyNote size={14} aria-hidden="true" />
          Add Note
        </button>
      </div>
    </div>
  );
}
