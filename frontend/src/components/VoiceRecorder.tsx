import { useEffect, useRef, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, Check, Clock, Mic, RotateCcw, Square } from "lucide-react";
import { Modal } from "./Modal";
import { StatusBadge } from "./StatusBadge";
import { useCareEvents } from "../state/CareEventsContext";
import { useReducedMotion } from "../lib/useReducedMotion";
import {
  fetchCareEventTimeline,
  requestAudioUploadUrl,
  uploadAudioToPresignedUrl,
  USE_MOCK_DATA,
} from "../data/api";
import type { CareEvent } from "../data/types";

type Stage = "idle" | "recording" | "uploading" | "processing" | "timeout" | "error" | "done";

// --- Mock-data-mode fallback only (VITE_ELDERLINK_USE_MOCK_DATA=true) ---
// Used purely for local UI work with no backend deployed. The real flow
// below it (recording -> presigned S3 upload -> poll the real read API)
// is what runs against the actual deployed ElderLink stack.
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

// Candidates in preference order - MediaRecorder.isTypeSupported reports
// what THIS browser can actually encode, never assumed. Chrome/Firefox
// report audio/webm; Safari reports audio/mp4; none reliably support wav/
// mp3 output directly from MediaRecorder.
const MIME_TYPE_CANDIDATES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/ogg;codecs=opus",
  "audio/ogg",
  "audio/mp4",
];

function pickSupportedMimeType(): string {
  if (typeof MediaRecorder === "undefined") return "";
  for (const candidate of MIME_TYPE_CANDIDATES) {
    if (MediaRecorder.isTypeSupported?.(candidate)) return candidate;
  }
  return ""; // let the browser pick its own default
}

// The backend's content-type allowlist only recognizes bare MIME types
// (no codec suffix) - see backend/lambdas/audio_upload_url/handler.py.
function baseContentType(mimeType: string): string {
  return mimeType.split(";")[0].trim();
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

// Bounded polling for the real event this recording produced - the
// pipeline is asynchronous (S3 -> EventBridge -> process_audio ->
// EventBridge -> extract_events -> DynamoDB), so there is no "upload
// finished, event exists" guarantee. Stops as soon as a genuinely new
// event id appears (never previously seen in this timeline), or gives up
// after a bounded number of attempts - never spins forever, never
// fabricates a result.
const POLL_INTERVAL_MS = 2500;
const POLL_MAX_ATTEMPTS = 8; // ~20s total - generous relative to the ~3-4s the real pipeline takes end to end

async function pollForNewEvent(
  preExistingIds: Set<string>,
  isCancelled: () => boolean,
): Promise<CareEvent | null> {
  for (let attempt = 0; attempt < POLL_MAX_ATTEMPTS; attempt++) {
    await sleep(POLL_INTERVAL_MS);
    if (isCancelled()) return null;
    try {
      const events = await fetchCareEventTimeline();
      const newEvent = events.find((e) => !preExistingIds.has(e.id));
      if (newEvent) return newEvent;
    } catch {
      // A transient read-API failure mid-poll isn't fatal on its own -
      // keep trying until POLL_MAX_ATTEMPTS is exhausted, same as a slow
      // pipeline; only a real, persistent failure surfaces as an error
      // (the "processing" stage's own timeout path covers that).
    }
    if (isCancelled()) return null;
  }
  return null;
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
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [foundEvent, setFoundEvent] = useState<CareEvent | null>(null);
  const pendingEvent = useRef<CareEvent | null>(null); // mock-mode path only
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const preExistingIdsRef = useRef<Set<string>>(new Set());
  const cancelledRef = useRef(false);
  const { addEvent, refresh, events } = useCareEvents();
  const reducedMotion = useReducedMotion();

  // Stop any in-flight polling and release the microphone if the recorder
  // unmounts mid-flow (e.g. the caregiver navigates away) - never leaves a
  // dangling poll loop or a live mic stream behind.
  useEffect(() => {
    return () => {
      cancelledRef.current = true;
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  useEffect(() => {
    if (!open) return;
    if (stage !== "recording") return;
    const id = window.setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => window.clearInterval(id);
  }, [open, stage]);

  // --- Mock-data-mode fallback: fake progress + fake extraction result ---
  useEffect(() => {
    if (!USE_MOCK_DATA) return;
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
    if (!USE_MOCK_DATA) return;
    if (stage === "uploading" && progress >= 100) {
      const t = window.setTimeout(() => setStage("processing"), 250);
      return () => window.clearTimeout(t);
    }
  }, [stage, progress]);

  useEffect(() => {
    if (!USE_MOCK_DATA) return;
    if (stage !== "processing") return;
    pendingEvent.current = buildMockEvent();
    const t = window.setTimeout(() => setStage("done"), 1600);
    return () => window.clearTimeout(t);
  }, [stage]);
  // --- end mock-data-mode fallback ---

  const startRecording = async () => {
    setErrorMessage(null);
    setElapsed(0);
    setOpen(true);

    if (USE_MOCK_DATA) {
      setStage("recording");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mimeType = pickSupportedMimeType();
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      setStage("recording");
    } catch {
      setErrorMessage(
        "Microphone access was denied or unavailable. Please allow microphone access in your browser and try again.",
      );
      setStage("error");
    }
  };

  const handleRealUpload = async (blob: Blob, contentType: string) => {
    setProgress(0);
    try {
      const { upload_url: uploadUrl } = await requestAudioUploadUrl(contentType);
      await uploadAudioToPresignedUrl(uploadUrl, blob, contentType, (fraction) =>
        setProgress(Math.round(fraction * 100)),
      );
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Upload failed. Please try again.");
      setStage("error");
      return;
    }

    setStage("processing");
    cancelledRef.current = false;
    const result = await pollForNewEvent(preExistingIdsRef.current, () => cancelledRef.current);
    if (cancelledRef.current) return;

    if (result) {
      setFoundEvent(result);
      refresh(); // syncs the shared CareEventsContext so every page reflects it, not just this modal
      setStage("done");
    } else {
      setStage("timeout");
    }
  };

  const stopRecording = () => {
    if (USE_MOCK_DATA) {
      setStage("uploading");
      return;
    }

    const recorder = mediaRecorderRef.current;
    if (!recorder) return;

    // Snapshot which event ids already exist BEFORE upload starts - this
    // is how the poller later recognizes "new" without guessing at
    // timing. Taken from the same CareEventsContext every other page
    // reads, not a second store.
    preExistingIdsRef.current = new Set(events.map((e) => e.id));

    recorder.onstop = () => {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      const mimeType = recorder.mimeType || "audio/webm";
      const blob = new Blob(chunksRef.current, { type: mimeType });
      void handleRealUpload(blob, baseContentType(mimeType));
    };
    recorder.stop();
    setStage("uploading");
  };

  const checkAgain = async () => {
    setStage("processing");
    cancelledRef.current = false;
    const result = await pollForNewEvent(preExistingIdsRef.current, () => cancelledRef.current);
    if (cancelledRef.current) return;
    if (result) {
      setFoundEvent(result);
      refresh();
      setStage("done");
    } else {
      setStage("timeout");
    }
  };

  const close = () => {
    cancelledRef.current = true;
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    streamRef.current?.getTracks().forEach((track) => track.stop());
    setOpen(false);
    window.setTimeout(() => {
      setStage("idle");
      setElapsed(0);
      setProgress(0);
      setErrorMessage(null);
      setFoundEvent(null);
      pendingEvent.current = null;
    }, 200);
  };

  const viewInStream = () => {
    if (USE_MOCK_DATA && pendingEvent.current) {
      addEvent(pendingEvent.current);
    }
    // Real mode: the event already came from the real API via refresh() -
    // nothing to add, just close and let the caregiver find it in the list.
    close();
  };

  const transition = reducedMotion ? { duration: 0 } : { duration: 0.18 };
  const displayEvent = USE_MOCK_DATA ? pendingEvent.current : foundEvent;

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
                  className="mt-6 inline-flex items-center gap-2 rounded-full px-5 py-3 text-[14px] font-semibold text-[var(--color-paper)] sm:py-2.5 sm:text-[13.5px]"
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
                  Processing note
                </h2>
                <span
                  className={`mt-6 h-9 w-9 rounded-full border-2 border-[var(--color-line)] border-t-[var(--color-teal)] ${
                    reducedMotion ? "" : "animate-spin"
                  }`}
                  aria-hidden="true"
                />
                <p className="mt-5 text-[13px] text-[var(--color-ink-muted)]">
                  {USE_MOCK_DATA
                    ? "Turning your voice note into a care event."
                    : "Transcribing and extracting a care event - this usually takes a few seconds."}
                </p>
              </motion.div>
            )}

            {stage === "timeout" && (
              <motion.div
                key="timeout"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={transition}
                className="flex flex-col items-center py-6 text-center"
              >
                <span
                  className="flex h-11 w-11 items-center justify-center rounded-full"
                  style={{ backgroundColor: "var(--color-amber-soft)", color: "var(--color-amber)" }}
                  aria-hidden="true"
                >
                  <Clock size={20} />
                </span>
                <h2 id="voice-recorder-title" className="font-display mt-3 text-[19px] text-[var(--color-ink)]">
                  Still processing
                </h2>
                <p className="mt-1.5 max-w-xs text-[13px] leading-relaxed text-[var(--color-ink-muted)]">
                  Your recording uploaded successfully, but it's taking longer than usual to appear. It will
                  show up automatically once ready - you can check again now or come back later.
                </p>
                <div className="mt-5 flex w-full flex-col gap-2 sm:flex-row sm:justify-center">
                  <button
                    type="button"
                    onClick={checkAgain}
                    className="inline-flex items-center justify-center gap-1.5 rounded-full px-5 py-3 text-[14px] font-semibold text-[var(--color-paper)] sm:py-2.5 sm:text-[13.5px]"
                    style={{ backgroundColor: "var(--color-teal)" }}
                  >
                    <RotateCcw size={14} aria-hidden="true" />
                    Check again
                  </button>
                  <button
                    type="button"
                    onClick={close}
                    className="rounded-full border px-5 py-3 text-[14px] font-semibold text-[var(--color-ink-soft)] sm:py-2.5 sm:text-[13.5px]"
                    style={{ borderColor: "var(--color-line)" }}
                  >
                    Close
                  </button>
                </div>
              </motion.div>
            )}

            {stage === "error" && (
              <motion.div
                key="error"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={transition}
                className="flex flex-col items-center py-6 text-center"
              >
                <span
                  className="flex h-11 w-11 items-center justify-center rounded-full"
                  style={{ backgroundColor: "var(--color-concern-soft)", color: "var(--color-concern)" }}
                  aria-hidden="true"
                >
                  <AlertTriangle size={20} />
                </span>
                <h2 id="voice-recorder-title" className="font-display mt-3 text-[19px] text-[var(--color-ink)]">
                  Something went wrong
                </h2>
                <p className="mt-1.5 max-w-xs text-[13px] leading-relaxed text-[var(--color-ink-muted)]">
                  {errorMessage ?? "We couldn't record or send that voice note."}
                </p>
                <div className="mt-5 flex w-full flex-col gap-2 sm:flex-row sm:justify-center">
                  <button
                    type="button"
                    onClick={startRecording}
                    className="inline-flex items-center justify-center gap-1.5 rounded-full px-5 py-3 text-[14px] font-semibold text-[var(--color-paper)] sm:py-2.5 sm:text-[13.5px]"
                    style={{ backgroundColor: "var(--color-teal)" }}
                  >
                    <Mic size={14} aria-hidden="true" />
                    Try again
                  </button>
                  <button
                    type="button"
                    onClick={close}
                    className="rounded-full border px-5 py-3 text-[14px] font-semibold text-[var(--color-ink-soft)] sm:py-2.5 sm:text-[13.5px]"
                    style={{ borderColor: "var(--color-line)" }}
                  >
                    Close
                  </button>
                </div>
              </motion.div>
            )}

            {stage === "done" && displayEvent && (
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
                    Update added
                  </h2>
                </div>
                <div
                  className="mt-4 rounded-xl border p-3.5"
                  style={{ borderColor: "var(--color-line)", backgroundColor: "var(--color-ivory-soft)" }}
                >
                  <p className="font-display text-[15px] text-[var(--color-ink)]">{displayEvent.title}</p>
                  <p className="mt-1 text-[13px] text-[var(--color-ink-muted)]">
                    {displayEvent.reportedBy} &middot; Just now
                  </p>
                  <div className="mt-2.5">
                    <StatusBadge status={displayEvent.status} size="sm" />
                  </div>
                </div>
                <button
                  type="button"
                  onClick={viewInStream}
                  className="mt-5 w-full rounded-full px-5 py-3 text-[14px] font-semibold text-[var(--color-paper)] sm:py-2.5 sm:text-[13.5px]"
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
