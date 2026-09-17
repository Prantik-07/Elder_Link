import { Mic } from "lucide-react";
import clsx from "clsx";
import type { CareEvent } from "../data/types";
import { CATEGORY_META } from "../lib/categoryMeta";
import { formatClock } from "../lib/format";
import { StatusBadge } from "./StatusBadge";

const DOT_COLOR: Record<CareEvent["status"], string> = {
  verified: "var(--color-verified)",
  needs_verification: "var(--color-amber)",
  uncertain: "var(--color-uncertain)",
};

export function TimelineEvent({
  event,
  selected,
  isLast,
  onSelect,
}: {
  event: CareEvent;
  selected: boolean;
  isLast: boolean;
  onSelect: () => void;
}) {
  const meta = CATEGORY_META[event.type];
  const Icon = meta.icon;
  const label = event.categoryLabel ?? meta.label;

  return (
    <li className="relative flex gap-4 pb-5 pl-1">
      <div className="flex w-4 flex-col items-center">
        <span
          className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ring-4"
          style={{
            backgroundColor: DOT_COLOR[event.status],
            // Use an rgba-ish ring via a soft background token so the dot reads
            // clearly against the ivory page background.
            boxShadow: "0 0 0 4px var(--color-ivory)",
          }}
          aria-hidden="true"
        />
        {!isLast && (
          <span
            className="mt-1 w-px flex-1"
            style={{ backgroundColor: "var(--color-line)" }}
            aria-hidden="true"
          />
        )}
      </div>

      <button
        type="button"
        onClick={onSelect}
        aria-current={selected}
        className={clsx(
          "min-w-0 flex-1 rounded-xl border px-4 py-3 text-left transition-colors",
          selected ? "shadow-[var(--shadow-card)]" : "border-transparent hover:bg-[var(--color-ivory-soft)]",
        )}
        style={
          selected
            ? { backgroundColor: "var(--color-paper)", borderColor: "var(--color-line)" }
            : undefined
        }
      >
        <div className="flex items-center justify-between gap-3">
          <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold tracking-wide uppercase" style={{ color: meta.iconColor }}>
            <Icon size={12} aria-hidden="true" />
            {label}
          </span>
          <span className="shrink-0 text-[12px] tabular-nums text-[var(--color-ink-muted)]">
            {formatClock(event.occurredAt)}
          </span>
        </div>
        <p className="font-display mt-1 text-[15px] leading-snug text-[var(--color-ink)]">
          {event.title}
        </p>
        <div className="mt-1.5 flex items-center justify-between gap-3">
          <span className="flex items-center gap-1.5 text-[12.5px] text-[var(--color-ink-muted)]">
            {event.evidence && <Mic size={11} aria-label="Has voice evidence" />}
            {event.reportedBy}
          </span>
          <StatusBadge status={event.status} size="sm" />
        </div>
      </button>
    </li>
  );
}
