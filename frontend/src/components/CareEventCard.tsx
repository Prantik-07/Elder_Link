import { ChevronRight, FileText, Mic } from "lucide-react";
import clsx from "clsx";
import type { CareEvent } from "../data/types";
import { CATEGORY_META } from "../lib/categoryMeta";
import { formatTimestamp } from "../lib/format";
import { StatusBadge } from "./StatusBadge";
import { CaregiverAvatar } from "./CaregiverAvatar";

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
          <span className="mt-0.5 block text-[13px] text-[var(--color-ink-soft)] line-clamp-2 lg:line-clamp-1">
            {event.summary}
          </span>
          <span className="mt-1.5 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[12px] text-[var(--color-ink-muted)]">
            <span className="flex items-center gap-1.5">
              <CaregiverAvatar reportedBy={event.reportedBy} size={16} />
              {event.reportedBy.split(" ")[0]}
            </span>
            <span>{formatTimestamp(event.occurredAt)}</span>
            {event.evidence && (
              <span className="flex items-center gap-1">
                <Mic size={11} aria-hidden="true" />
                Voice note
              </span>
            )}
            {event.evidence && (
              <span className="flex items-center gap-1">
                <FileText size={11} aria-hidden="true" />1 evidence item
              </span>
            )}
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
