import { AnimatePresence, motion } from "framer-motion";
import { useCareEvents } from "../state/CareEventsContext";
import {
  MobileEventSheet,
  SelectedEvidence,
  useEscapeToClose,
  useSlideMotion,
} from "./EventDetailPanel";

/**
 * Evidence/verification view for the selected event on the Care homepage.
 * On desktop it slides in over the right rail from the edge of the page
 * container (clipped there, not the viewport; overflow-clip keeps the sticky panel working); below lg it's a full-screen sheet.
 * Render inside a `relative` page container.
 */
export function EventDetailDrawer() {
  const { selectedId } = useCareEvents();
  const motionProps = useSlideMotion();
  useEscapeToClose();

  return (
    <>
      <div
        className="pointer-events-none absolute inset-y-0 right-0 z-20 hidden w-[26rem] overflow-clip lg:block"
        aria-label="Event detail"
      >
        <AnimatePresence>
          {selectedId && (
            <motion.div
              className="pointer-events-auto sticky top-16 h-[calc(100vh-4rem)] border-l bg-[var(--color-paper)] shadow-[var(--shadow-panel)]"
              style={{ borderColor: "var(--color-line)" }}
              role="dialog"
              aria-label="Event detail"
              {...motionProps}
            >
              <SelectedEvidence />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      <MobileEventSheet />
    </>
  );
}
