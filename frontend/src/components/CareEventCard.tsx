import { ChevronRight, Mic } from "lucide-react";
import clsx from "clsx";
import type { CareEvent } from "../data/types";
import { CATEGORY_META } from "../lib/categoryMeta";
import { formatTimestamp } from "../lib/format";
import { StatusBadge } from "./StatusBadge";

export function CareEventCard({
  event,
  selected,
  onSelect,
}: {
  event: CareEvent;
  selected: boolean;
  onSelect: () => void;
}) {
  const meta = CATEGORY_META[event.type];
  const Icon = meta.icon;
  const label = event.categoryLabel ?? meta.label;
  const isFlagged = event.status === "needs_verification";

  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        aria-current={selected}
        className={clsx(
          "group flex w-full items-start gap-3.5 rounded-xl border px-4 py-3.5 text-left transition-colors sm:items-center",
          selected
            ? "shadow-[var(--shadow-card)]"
            : "border-transparent hover:bg-[var(--color-ivory-soft)]",
        )}
        style={
          selected
            ? {
                backgroundColor: isFlagged ? "var(--color-amber-soft)" : "var(--color-paper)",
                borderColor: isFlagged ? "var(--color-amber-line)" : "var(--color-line)",
              }
            : undefined
        }
      >
        <span
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full"
          style={{ backgroundColor: meta.iconBg, color: meta.iconColor }}
          aria-hidden="true"
        >
          <Icon size={18} strokeWidth={2} />
        </span>

        <span className="min-w-0 flex-1">
          <span
            className="block text-[11px] font-semibold tracking-wide uppercase"
            style={{ color: isFlagged ? "var(--color-amber)" : meta.iconColor }}
          >
            {label}
          </span>
          <span className="font-display mt-0.5 block text-[15.5px] leading-snug text-[var(--color-ink)]">
            {event.title}
          </span>
          <span className="mt-1 flex flex-wrap items-center gap-x-1.5 text-[12.5px] text-[var(--color-ink-muted)]">
            {event.evidence && (
              <Mic size={11} className="shrink-0" aria-label="Has voice evidence" />
            )}
            <span>{event.reportedBy}</span>
            <span aria-hidden="true">&middot;</span>
            <span>{formatTimestamp(event.occurredAt)}</span>
          </span>
        </span>

        <span className="ml-2 flex shrink-0 flex-col items-end gap-2 sm:flex-row sm:items-center">
          <StatusBadge status={event.status} size="sm" />
          <ChevronRight
            size={16}
            className="hidden text-[var(--color-ink-muted)] transition-transform group-hover:translate-x-0.5 sm:block"
            aria-hidden="true"
          />
        </span>
      </button>
    </li>
  );
}
