import { useEffect } from "react";
import { createPortal } from "react-dom";
import { useCareEvents } from "../state/CareEventsContext";
import { EvidencePanel } from "./EvidencePanel";

/**
 * Full evidence/verification view for the selected event, shown as an
 * overlay on top of the Care homepage (rather than a persistent side
 * column) so the homepage's right rail can stay dedicated to quick
 * actions and personalization, matching the approved reference layout.
 */
export function EventDetailDrawer() {
  const { selectedEvent, selectEvent, setStatus } = useCareEvents();

  useEffect(() => {
    if (!selectedEvent) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") selectEvent(null);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [selectedEvent, selectEvent]);

  if (!selectedEvent) return null;

  return createPortal(
    <div className="fixed inset-0 z-40">
      <div
        className="absolute inset-0 bg-[var(--color-ink)]/35 backdrop-blur-[1px]"
        onClick={() => selectEvent(null)}
        aria-hidden="true"
      />
      <div
        className="absolute inset-y-0 right-0 flex w-full max-w-full flex-col bg-[var(--color-paper)] shadow-[var(--shadow-panel)] sm:max-w-[26rem]"
        role="dialog"
        aria-modal="true"
        aria-label="Event detail"
      >
        <EvidencePanel
          event={selectedEvent}
          onClose={() => selectEvent(null)}
          onSetStatus={(status) => setStatus(selectedEvent.id, status)}
        />
      </div>
    </div>,
    document.body,
  );
}
