import type { ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { FileSearch } from "lucide-react";
import { useCareEvents } from "../state/CareEventsContext";
import {
  MobileEventSheet,
  SelectedEvidence,
  useEscapeToClose,
  useSlideMotion,
} from "./EventDetailPanel";

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
  const { selectedId } = useCareEvents();
  const motionProps = useSlideMotion();
  useEscapeToClose();

  return (
    <div className="mx-auto flex max-w-[1440px]">
      <div className="min-w-0 flex-1 px-4 py-5 sm:px-6 sm:py-7 lg:px-8 lg:py-9 xl:px-10">{children}</div>

      {/* overflow-hidden clips the slide to the content area's right edge. */}
      <aside
        className="sticky top-16 hidden h-[calc(100vh-4rem)] w-[28rem] shrink-0 overflow-hidden border-l lg:block xl:w-[30rem]"
        style={{ borderColor: "var(--color-line)" }}
        aria-label="Event detail"
      >
        <DetailPlaceholder />
        <AnimatePresence>
          {selectedId && (
            <motion.div className="absolute inset-0 bg-[var(--color-paper)]" {...motionProps}>
              <SelectedEvidence />
            </motion.div>
          )}
        </AnimatePresence>
      </aside>

      <MobileEventSheet />
    </div>
  );
}
