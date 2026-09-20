import { useMemo, useState } from "react";
import { Calendar, Check, ClipboardCheck, TriangleAlert } from "lucide-react";
import { useCareEvents } from "../state/CareEventsContext";
import { CareDetailLayout } from "../components/CareDetailLayout";
import { EmptyState } from "../components/EmptyState";
import { HandoffEventRow } from "../components/HandoffEventRow";
import { Modal } from "../components/Modal";
import { lastHandoffCutoff, LAST_HANDOFF_LABEL } from "../lib/handoff";

const UPCOMING_ITEMS = [
  {
    id: "up-1",
    label: "Cardiology follow-up with Dr. Mehta",
    when: "Tuesday, 10:30 AM",
  },
  {
    id: "up-2",
    label: "Check in on new blood-pressure medication tolerance",
    when: "Recommended within 3 days",
  },
];

export function HandoffPage() {
  const { events, isLoading, error, selectedId, toggleEvent } = useCareEvents();
  const [reviewOpen, setReviewOpen] = useState(false);
  const [confirmed, setConfirmed] = useState(false);

  const sinceHandoff = useMemo(() => {
    const cutoff = lastHandoffCutoff();
    return events
      .filter((e) => new Date(e.occurredAt) > cutoff)
      .sort((a, b) => new Date(b.occurredAt).getTime() - new Date(a.occurredAt).getTime());
  }, [events]);

  const needsAttention = sinceHandoff.filter(
    (e) => e.status === "needs_verification" || e.status === "uncertain",
  );
  const importantChanges = sinceHandoff.filter((e) => e.status === "verified");

  const openReview = () => {
    setConfirmed(false);
    setReviewOpen(true);
  };

  if (isLoading || error) {
    return (
      <CareDetailLayout>
        <div className="flex flex-col gap-8">
          <h1 className="font-display text-[28px] text-[var(--color-ink)]">Handoff</h1>
          <EmptyState
            message={isLoading ? "Loading care events..." : `Couldn't load care events: ${error}`}
          />
        </div>
      </CareDetailLayout>
    );
  }

  return (
    <CareDetailLayout>
      <div className="flex flex-col gap-8">
        <section className="order-1 lg:order-none">
          <h1 className="font-display text-[28px] text-[var(--color-ink)]">Handoff</h1>
          <p className="mt-1.5 max-w-xl text-[14px] leading-relaxed text-[var(--color-ink-soft)]">
            What the next caregiver needs to know since your last handoff, {LAST_HANDOFF_LABEL}.
          </p>

          <div className="mt-4 flex flex-wrap gap-3">
            <span
              className="inline-flex items-center gap-2 rounded-full border px-4 py-2 text-[13.5px] font-medium"
              style={{ borderColor: "var(--color-line)", backgroundColor: "var(--color-paper)" }}
            >
              <span className="font-display text-[15px] text-[var(--color-ink)]">
                {sinceHandoff.length}
              </span>
              <span className="text-[var(--color-ink-muted)]">
                {sinceHandoff.length === 1 ? "change" : "changes"}
              </span>
            </span>
            <span
              className="inline-flex items-center gap-2 rounded-full border px-4 py-2 text-[13.5px] font-medium"
              style={{ borderColor: "var(--color-amber-line)", backgroundColor: "var(--color-amber-soft)" }}
            >
              <span className="font-display text-[15px]" style={{ color: "var(--color-amber)" }}>
                {needsAttention.length}
              </span>
              <span style={{ color: "var(--color-amber)" }}>needs verification</span>
            </span>
          </div>
        </section>

        <section className="order-3 lg:order-none">
          <h2 className="mb-2.5 text-[13px] font-semibold tracking-wide text-[var(--color-ink)] uppercase">
            Important changes
          </h2>
          {importantChanges.length === 0 ? (
            <EmptyState message="No verified changes since your last handoff." />
          ) : (
            <ul className="flex flex-col gap-2">
              {importantChanges.map((e) => (
                <HandoffEventRow
                  key={e.id}
                  event={e}
                  selected={e.id === selectedId}
                  onSelect={() => toggleEvent(e.id)}
                />
              ))}
            </ul>
          )}
        </section>

        <section className="order-2 lg:order-none">
          <h2
            className="mb-2.5 flex items-center gap-1.5 text-[13px] font-semibold tracking-wide uppercase"
            style={{ color: "var(--color-amber)" }}
          >
            <TriangleAlert size={13} aria-hidden="true" />
            Needs attention
          </h2>
          {needsAttention.length === 0 ? (
            <EmptyState message="Nothing outstanding - all clear." />
          ) : (
            <ul className="flex flex-col gap-2">
              {needsAttention.map((e) => (
                <HandoffEventRow
                  key={e.id}
                  event={e}
                  selected={e.id === selectedId}
                  onSelect={() => toggleEvent(e.id)}
                />
              ))}
            </ul>
          )}
        </section>

        <section className="order-4 lg:order-none">
          <h2 className="mb-2.5 flex items-center gap-1.5 text-[13px] font-semibold tracking-wide text-[var(--color-ink)] uppercase">
            <Calendar size={13} aria-hidden="true" />
            Upcoming items
          </h2>
          <ul className="flex flex-col gap-2">
            {UPCOMING_ITEMS.map((item) => (
              <li
                key={item.id}
                className="flex items-center justify-between gap-3 rounded-xl border px-4 py-3"
                style={{ borderColor: "var(--color-line)" }}
              >
                <span className="text-[14px] text-[var(--color-ink)]">{item.label}</span>
                <span className="shrink-0 text-[12.5px] text-[var(--color-ink-muted)]">{item.when}</span>
              </li>
            ))}
          </ul>
        </section>

        <div className="order-5 border-t pt-6 lg:order-none" style={{ borderColor: "var(--color-line)" }}>
          <button
            type="button"
            onClick={openReview}
            className="flex w-full items-center justify-center gap-2 rounded-full px-5 py-3.5 text-[14.5px] font-semibold text-[var(--color-paper)] transition-opacity hover:opacity-90 sm:inline-flex sm:w-auto sm:py-2.5 sm:text-[14px]"
            style={{ backgroundColor: "var(--color-teal)" }}
          >
            <ClipboardCheck size={16} aria-hidden="true" />
            Review handoff
          </button>
        </div>
      </div>

      {reviewOpen && (
        <Modal onClose={() => setReviewOpen(false)} titleId="handoff-review-title">
          {!confirmed ? (
            <>
              <h2 id="handoff-review-title" className="font-display text-[20px] text-[var(--color-ink)]">
                Confirm this handoff
              </h2>
              <p className="mt-1.5 text-[13.5px] text-[var(--color-ink-soft)]">
                The next caregiver will see {sinceHandoff.length}{" "}
                {sinceHandoff.length === 1 ? "change" : "changes"}, including{" "}
                {needsAttention.length} that still {needsAttention.length === 1 ? "needs" : "need"}{" "}
                verification.
              </p>
              <ul className="mt-4 flex flex-col gap-1.5 text-[13.5px] text-[var(--color-ink)]">
                {sinceHandoff.slice(0, 4).map((e) => (
                  <li key={e.id} className="flex items-center gap-2">
                    <span
                      className="h-1.5 w-1.5 shrink-0 rounded-full"
                      style={{
                        backgroundColor:
                          e.status === "verified" ? "var(--color-verified)" : "var(--color-amber)",
                      }}
                      aria-hidden="true"
                    />
                    <span className="truncate">{e.title}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-6 flex flex-col gap-2.5 sm:flex-row">
                <button
                  type="button"
                  onClick={() => setConfirmed(true)}
                  className="flex w-full items-center justify-center gap-1.5 rounded-full px-5 py-3 text-[13.5px] font-semibold text-[var(--color-paper)] sm:w-auto sm:py-2.5"
                  style={{ backgroundColor: "var(--color-teal)" }}
                >
                  <Check size={14} aria-hidden="true" />
                  Confirm handoff
                </button>
                <button
                  type="button"
                  onClick={() => setReviewOpen(false)}
                  className="w-full rounded-full border px-5 py-3 text-[13.5px] font-semibold text-[var(--color-ink-soft)] sm:w-auto sm:py-2.5"
                  style={{ borderColor: "var(--color-line)" }}
                >
                  Cancel
                </button>
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center py-2 text-center">
              <span
                className="flex h-12 w-12 items-center justify-center rounded-full"
                style={{ backgroundColor: "var(--color-verified-soft)", color: "var(--color-verified)" }}
                aria-hidden="true"
              >
                <Check size={22} strokeWidth={2.5} />
              </span>
              <h2 id="handoff-review-title" className="font-display mt-3 text-[19px] text-[var(--color-ink)]">
                Handoff confirmed
              </h2>
              <p className="mt-1.5 text-[13.5px] text-[var(--color-ink-soft)]">
                The next caregiver now has everything from this handoff.
              </p>
              <button
                type="button"
                onClick={() => setReviewOpen(false)}
                className="mt-5 w-full rounded-full px-5 py-3 text-[13.5px] font-semibold text-[var(--color-paper)] sm:w-auto sm:py-2.5"
                style={{ backgroundColor: "var(--color-teal)" }}
              >
                Done
              </button>
            </div>
          )}
        </Modal>
      )}
    </CareDetailLayout>
  );
}
