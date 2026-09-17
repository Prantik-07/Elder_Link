import { Mic } from "lucide-react";
import type { CareEvent } from "../data/types";
import { CATEGORY_META } from "../lib/categoryMeta";
import { formatTimestamp } from "../lib/format";
import { StatusBadge } from "./StatusBadge";

export function HandoffEventRow({
  event,
  onSelect,
}: {
  event: CareEvent;
  onSelect: () => void;
}) {
  const meta = CATEGORY_META[event.type];
  const Icon = meta.icon;
  const label = event.categoryLabel ?? meta.label;

  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        className="flex w-full items-start gap-3 rounded-xl border px-4 py-3 text-left transition-colors hover:bg-[var(--color-ivory-soft)]"
        style={{ borderColor: "var(--color-line)" }}
      >
        <span
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full"
          style={{ backgroundColor: meta.iconBg, color: meta.iconColor }}
          aria-hidden="true"
        >
          <Icon size={16} strokeWidth={2} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[11px] font-semibold tracking-wide uppercase" style={{ color: meta.iconColor }}>
            {label}
          </span>
          <span className="font-display mt-0.5 block text-[14.5px] leading-snug text-[var(--color-ink)]">
            {event.title}
          </span>
          <span className="mt-1 flex items-center gap-1.5 text-[12px] text-[var(--color-ink-muted)]">
            {event.evidence && <Mic size={10} aria-label="Has voice evidence" />}
            {event.reportedBy} &middot; {formatTimestamp(event.occurredAt)}
          </span>
        </span>
        <StatusBadge status={event.status} size="sm" />
      </button>
    </li>
  );
}
