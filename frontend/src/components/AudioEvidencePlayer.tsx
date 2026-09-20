import { useEffect, useMemo, useRef, useState } from "react";
import { Pause, Play } from "lucide-react";
import { formatDuration } from "../lib/format";

const SPEEDS = [1, 1.5, 2] as const;

// Deterministic pseudo-waveform bar heights, seeded from the segment id so
// the same evidence clip always renders the same "shape" across renders.
function waveformBars(seed: string, count = 46): number[] {
  let x = 0;
  for (let i = 0; i < seed.length; i++) x = (x * 31 + seed.charCodeAt(i)) >>> 0;
  const bars: number[] = [];
  for (let i = 0; i < count; i++) {
    x = (x * 1103515245 + 12345) >>> 0;
    const t = (x / 0xffffffff) * Math.PI * 2;
    const height = 0.3 + 0.65 * Math.abs(Math.sin(t * 2.3 + i * 0.6));
    bars.push(height);
  }
  return bars;
}

export function AudioEvidencePlayer({
  segmentId,
  durationSeconds,
}: {
  segmentId: string;
  durationSeconds: number;
}) {
  const [playing, setPlaying] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [speedIndex, setSpeedIndex] = useState(0);
  const bars = useMemo(() => waveformBars(segmentId), [segmentId]);
  const reduceMotion = useRef(
    typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches,
  );

  useEffect(() => {
    if (!playing) return;
    const speed = SPEEDS[speedIndex];
    const tickMs = 200;
    const id = window.setInterval(() => {
      setElapsed((prev) => {
        const next = prev + (tickMs / 1000) * speed;
        if (next >= durationSeconds) {
          setPlaying(false);
          return durationSeconds;
        }
        return next;
      });
    }, tickMs);
    return () => window.clearInterval(id);
  }, [playing, speedIndex, durationSeconds]);

  const progress = durationSeconds > 0 ? Math.min(1, elapsed / durationSeconds) : 0;

  const togglePlay = () => {
    if (!playing && elapsed >= durationSeconds) setElapsed(0);
    setPlaying((p) => !p);
  };

  const cycleSpeed = () => setSpeedIndex((i) => (i + 1) % SPEEDS.length);

  const seekTo = (ratio: number) => {
    setElapsed(Math.max(0, Math.min(durationSeconds, ratio * durationSeconds)));
  };

  return (
    <div
      className="flex items-center gap-3 rounded-xl border px-3.5 py-3"
      style={{ borderColor: "var(--color-line)", backgroundColor: "var(--color-ivory-soft)" }}
    >
      <button
        type="button"
        onClick={togglePlay}
        aria-label={playing ? "Pause evidence audio" : "Play evidence audio"}
        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-[var(--color-paper)] transition-transform active:scale-95 lg:h-9 lg:w-9"
        style={{ backgroundColor: "var(--color-teal)" }}
      >
        {playing ? (
          <Pause size={15} fill="currentColor" aria-hidden="true" />
        ) : (
          <Play size={15} fill="currentColor" className="ml-0.5" aria-hidden="true" />
        )}
      </button>

      <button
        type="button"
        onClick={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          seekTo((e.clientX - rect.left) / rect.width);
        }}
        aria-label="Seek evidence audio"
        role="slider"
        aria-valuemin={0}
        aria-valuemax={durationSeconds}
        aria-valuenow={Math.round(elapsed)}
        className="relative flex h-10 flex-1 items-center gap-[2px] overflow-hidden rounded lg:h-8"
      >
        {bars.map((h, i) => {
          const played = i / bars.length <= progress;
          return (
            <span
              key={i}
              className={reduceMotion.current ? "" : "transition-colors duration-150"}
              style={{
                height: `${h * 100}%`,
                width: "3px",
                borderRadius: "2px",
                backgroundColor: played ? "var(--color-teal)" : "var(--color-line)",
              }}
            />
          );
        })}
      </button>

      <span className="w-20 shrink-0 text-right text-[12px] tabular-nums text-[var(--color-ink-muted)]">
        {formatDuration(elapsed)} / {formatDuration(durationSeconds)}
      </span>

      <button
        type="button"
        onClick={cycleSpeed}
        className="shrink-0 rounded-full border px-2.5 py-2 text-[12px] font-semibold tabular-nums text-[var(--color-ink-soft)] lg:py-1"
        style={{ borderColor: "var(--color-line)" }}
        aria-label="Playback speed"
      >
        {SPEEDS[speedIndex]}x
      </button>
    </div>
  );
}
