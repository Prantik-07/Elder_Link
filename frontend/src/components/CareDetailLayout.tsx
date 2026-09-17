import type { ReactNode } from "react";
import { FileSearch } from "lucide-react";
import { useCareEvents } from "../state/CareEventsContext";
import { EvidencePanel } from "./EvidencePanel";

function DetailPlaceholder() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2.5 px-6 text-center">
      <FileSearch size={22} className="text-[var(--color-ink-muted)]" aria-hidden="true" />
      <p className="text-[13.5px] text-[var(--color-ink-muted)]">
        Select an update to see its evidence and verification status.
      </p>
    </div>
  );
}

export function CareDetailLayout({ children }: { children: ReactNode }) {
  const { selectedEvent, selectEvent, setStatus } = useCareEvents();

  return (
    <div className="mx-auto flex max-w-[1440px]">
      <div className="min-w-0 flex-1 px-6 py-7 sm:px-8 lg:py-9 xl:px-10">{children}</div>

      <aside
        className="sticky top-16 hidden h-[calc(100vh-4rem)] w-[28rem] shrink-0 border-l lg:block xl:w-[30rem]"
        style={{ borderColor: "var(--color-line)" }}
        aria-label="Event detail"
      >
        {selectedEvent ? (
          <EvidencePanel
            event={selectedEvent}
            onClose={() => selectEvent(null)}
            onSetStatus={(status) => setStatus(selectedEvent.id, status)}
          />
        ) : (
          <DetailPlaceholder />
        )}
      </aside>

      {selectedEvent && (
        <div className="fixed inset-0 z-40 bg-[var(--color-paper)] lg:hidden">
          <EvidencePanel
            event={selectedEvent}
            onClose={() => selectEvent(null)}
            onSetStatus={(status) => setStatus(selectedEvent.id, status)}
          />
        </div>
      )}
    </div>
  );
}
