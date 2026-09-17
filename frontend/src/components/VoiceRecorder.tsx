import { useEffect, useRef, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, Mic, Square } from "lucide-react";
import { Modal } from "./Modal";
import { StatusBadge } from "./StatusBadge";
import { useCareEvents } from "../state/CareEventsContext";
import { useReducedMotion } from "../lib/useReducedMotion";
import type { CareEvent } from "../data/types";

type Stage = "idle" | "recording" | "uploading" | "processing" | "done";

const MOCK_TRANSCRIPT =
  "Just checking in - Dad had his afternoon snack and is resting in the living room now. Seemed calm and comfortable.";

function buildMockEvent(): CareEvent {
  return {
    id: `evt-voice-${Date.now()}`,
    type: "observation",
    title: "Afternoon check-in: resting comfortably.",
    summary: "Had a snack, calm and comfortable in the living room.",
    whatHappened:
      "Caregiver recorded a quick afternoon check-in noting Dad had a snack and is resting comfortably.",
    occurredAt: new Date().toISOString(),
    reportedBy: "Shivaansh (Caregiver)",
    location: "At home",
    status: "needs_verification",
    verificationReason:
      "This update was just captured and hasn't been reviewed yet - confirm the details before it's included in a handoff.",
    evidence: {
      transcript: MOCK_TRANSCRIPT,
      segmentId: `seg-voice-${Date.now()}`,
      durationSeconds: 16,
    },
  };
}

function formatSeconds(s: number): string {
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

export function VoiceRecorder({
  renderTrigger,
}: {
  /** Custom trigger UI (e.g. the quick-actions rail's card). Defaults to a small pill button. */
  renderTrigger?: (onClick: () => void) => ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [stage, setStage] = useState<Stage>("idle");
  const [elapsed, setElapsed] = useState(0);
  const [progress, setProgress] = useState(0);
  const pendingEvent = useRef<CareEvent | null>(null);
  const { addEvent } = useCareEvents();
  const reducedMotion = useReducedMotion();

  useEffect(() => {
    if (!open) return;
    if (stage !== "recording") return;
    const id = window.setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => window.clearInterval(id);
  }, [open, stage]);

  useEffect(() => {
    if (stage !== "uploading") return;
    setProgress(0);
    const id = window.setInterval(() => {
      setProgress((p) => {
        if (p >= 100) {
          window.clearInterval(id);
          return 100;
        }
        return Math.min(100, p + 14);
      });
    }, 120);
    return () => window.clearInterval(id);
  }, [stage]);

  useEffect(() => {
    if (stage === "uploading" && progress >= 100) {
      const t = window.setTimeout(() => setStage("processing"), 250);
      return () => window.clearTimeout(t);
    }
  }, [stage, progress]);

  useEffect(() => {
    if (stage !== "processing") return;
    pendingEvent.current = buildMockEvent();
    const t = window.setTimeout(() => setStage("done"), 1600);
    return () => window.clearTimeout(t);
  }, [stage]);

  const startRecording = () => {
    setElapsed(0);
    setStage("recording");
    setOpen(true);
  };

  const stopRecording = () => setStage("uploading");

  const close = () => {
    setOpen(false);
    window.setTimeout(() => {
      setStage("idle");
      setElapsed(0);
      setProgress(0);
    }, 200);
  };

  const viewInStream = () => {
    if (pendingEvent.current) addEvent(pendingEvent.current);
    close();
  };

  const transition = reducedMotion ? { duration: 0 } : { duration: 0.18 };

  return (
    <>
      {renderTrigger ? (
        renderTrigger(startRecording)
      ) : (
        <button
          type="button"
          onClick={startRecording}
          className="inline-flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-[13px] font-medium text-[var(--color-ink-soft)] transition-colors hover:border-[var(--color-teal)]/40 hover:text-[var(--color-ink)]"
          style={{ borderColor: "var(--color-line)" }}
        >
          <Mic size={14} aria-hidden="true" />
          Record voice note
        </button>
      )}

      {open && (
        <Modal onClose={close} titleId="voice-recorder-title">
          <AnimatePresence mode="wait">
            {stage === "recording" && (
              <motion.div
                key="recording"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={transition}
                className="flex flex-col items-center py-4 text-center"
              >
                <h2 id="voice-recorder-title" className="font-display text-[19px] text-[var(--color-ink)]">
                  Recording voice note
                </h2>
                <div className="relative my-6 flex h-20 w-20 items-center justify-center">
                  {!reducedMotion && (
                    <span
                      className="absolute inset-0 animate-ping rounded-full"
                      style={{ backgroundColor: "var(--color-concern-soft)" }}
                      aria-hidden="true"
                    />
                  )}
                  <span
                    className="relative flex h-16 w-16 items-center justify-center rounded-full"
                    style={{ backgroundColor: "var(--color-concern)" }}
                  >
                    <Mic size={24} className="text-[var(--color-paper)]" aria-hidden="true" />
                  </span>
                </div>
                <p className="tabular-nums text-[15px] font-medium text-[var(--color-ink)]" aria-live="polite">
                  {formatSeconds(elapsed)}
                </p>
                <p className="mt-1 text-[13px] text-[var(--color-ink-muted)]">Speak naturally - we'll capture the details.</p>
                <button
                  type="button"
                  onClick={stopRecording}
                  className="mt-6 inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-[13.5px] font-semibold text-[var(--color-paper)]"
                  style={{ backgroundColor: "var(--color-teal)" }}
                >
                  <Square size={13} fill="currentColor" aria-hidden="true" />
                  Stop &amp; send
                </button>
              </motion.div>
            )}

            {stage === "uploading" && (
              <motion.div
                key="uploading"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={transition}
                className="py-6 text-center"
              >
                <h2 id="voice-recorder-title" className="font-display text-[19px] text-[var(--color-ink)]">
                  Uploading voice note
                </h2>
                <p className="mt-1.5 text-[13px] text-[var(--color-ink-muted)]">
                  Sending securely to ElderLink...
                </p>
                <div
                  className="mt-6 h-1.5 w-full overflow-hidden rounded-full"
                  style={{ backgroundColor: "var(--color-line-soft)" }}
                  role="progressbar"
                  aria-valuenow={progress}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <div
                    className="h-full rounded-full transition-[width] duration-150 ease-out"
                    style={{ width: `${progress}%`, backgroundColor: "var(--color-teal)" }}
                  />
                </div>
              </motion.div>
            )}

            {stage === "processing" && (
              <motion.div
                key="processing"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={transition}
                className="flex flex-col items-center py-8 text-center"
              >
                <h2 id="voice-recorder-title" className="font-display text-[19px] text-[var(--color-ink)]">
                  Transcribing...
                </h2>
                <span
                  className={`mt-6 h-9 w-9 rounded-full border-2 border-[var(--color-line)] border-t-[var(--color-teal)] ${
                    reducedMotion ? "" : "animate-spin"
                  }`}
                  aria-hidden="true"
                />
                <p className="mt-5 text-[13px] text-[var(--color-ink-muted)]">
                  Turning your voice note into a care event.
                </p>
              </motion.div>
            )}

            {stage === "done" && pendingEvent.current && (
              <motion.div
                key="done"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={transition}
              >
                <div className="flex items-center gap-2">
                  <span
                    className="flex h-8 w-8 items-center justify-center rounded-full"
                    style={{ backgroundColor: "var(--color-verified-soft)", color: "var(--color-verified)" }}
                    aria-hidden="true"
                  >
                    <Check size={16} strokeWidth={2.5} />
                  </span>
                  <h2 id="voice-recorder-title" className="font-display text-[19px] text-[var(--color-ink)]">
                    Care event created
                  </h2>
                </div>
                <div
                  className="mt-4 rounded-xl border p-3.5"
                  style={{ borderColor: "var(--color-line)", backgroundColor: "var(--color-ivory-soft)" }}
                >
                  <p className="font-display text-[15px] text-[var(--color-ink)]">
                    {pendingEvent.current.title}
                  </p>
                  <p className="mt-1 text-[13px] text-[var(--color-ink-muted)]">
                    {pendingEvent.current.reportedBy} &middot; Just now
                  </p>
                  <div className="mt-2.5">
                    <StatusBadge status={pendingEvent.current.status} size="sm" />
                  </div>
                </div>
                <button
                  type="button"
                  onClick={viewInStream}
                  className="mt-5 w-full rounded-full px-5 py-2.5 text-[13.5px] font-semibold text-[var(--color-paper)]"
                  style={{ backgroundColor: "var(--color-teal)" }}
                >
                  View in Care stream
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </Modal>
      )}
    </>
  );
}
