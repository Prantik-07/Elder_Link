import { useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useCareEvents } from "../state/CareEventsContext";
import { useReducedMotion } from "../lib/useReducedMotion";
import { EvidencePanel } from "./EvidencePanel";

const SLIDE_MS = 0.28;
const FADE_MS = 0.14;

/** Slide from the right edge of the panel's clipping container: translateX + opacity, ease-out. */
export function useSlideMotion() {
  const reduced = useReducedMotion();
  return {
    initial: reduced ? { opacity: 0 } : { opacity: 0, x: 48 },
    animate: { opacity: 1, x: 0 },
    exit: reduced ? { opacity: 0 } : { opacity: 0, x: 48 },
    transition: { duration: reduced ? FADE_MS : SLIDE_MS, ease: "easeOut" as const },
  };
}

/** Selected event's evidence, crossfading when the selection changes while the panel stays open. */
export function SelectedEvidence() {
  const { selectedEvent, selectEvent, setStatus } = useCareEvents();
  if (!selectedEvent) return null;

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={selectedEvent.id}
        className="h-full"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: FADE_MS, ease: "easeOut" }}
      >
        <EvidencePanel
          event={selectedEvent}
          onClose={() => selectEvent(null)}
          onSetStatus={(status) => setStatus(selectedEvent.id, status)}
        />
      </motion.div>
    </AnimatePresence>
  );
}

export function useEscapeToClose() {
  const { selectedId, selectEvent } = useCareEvents();
  useEffect(() => {
    if (!selectedId) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") selectEvent(null);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [selectedId, selectEvent]);
}

/** Phone/tablet full-screen sheet used by every page below the lg breakpoint. */
export function MobileEventSheet() {
  const { selectedId, selectEvent } = useCareEvents();
  const motionProps = useSlideMotion();

  return (
    <AnimatePresence>
      {selectedId && (
        <div className="fixed inset-0 z-40 overflow-hidden lg:hidden">
          <motion.div
            className="absolute inset-0 bg-[var(--color-ink)]/35"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: FADE_MS }}
            onClick={() => selectEvent(null)}
            aria-hidden="true"
          />
          <motion.div
            className="absolute inset-y-0 right-0 w-full bg-[var(--color-paper)] shadow-[var(--shadow-panel)] sm:max-w-[26rem]"
            role="dialog"
            aria-modal="true"
            aria-label="Event detail"
            {...motionProps}
          >
            <SelectedEvidence />
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
