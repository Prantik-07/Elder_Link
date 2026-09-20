import { Mic } from "lucide-react";
import type { CareEvent } from "../data/types";
import { CATEGORY_META } from "../lib/categoryMeta";
import { formatTimestamp } from "../lib/format";
import { StatusBadge } from "./StatusBadge";
import { CaregiverAvatar } from "./CaregiverAvatar";

export function HandoffEventRow({
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

  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        aria-current={selected}
        className="flex w-full items-start gap-3 rounded-xl border px-4 py-3 text-left transition-colors hover:bg-[var(--color-ivory-soft)]"
        style={{
          borderColor: selected ? "var(--color-teal)" : "var(--color-line)",
          backgroundColor: selected ? "var(--color-paper)" : undefined,
          boxShadow: selected ? "var(--shadow-card)" : undefined,
        }}
      >
        <span
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px]"
          style={{ backgroundColor: meta.iconBg, color: meta.iconColor }}
          aria-hidden="true"
        >
          <Icon size={16} strokeWidth={2} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[12px] font-semibold tracking-wide uppercase" style={{ color: meta.iconColor }}>
            {label}
          </span>
          <span className="font-display mt-0.5 block text-[14.5px] leading-snug text-[var(--color-ink)]">
            {event.title}
          </span>
          <span className="mt-1 flex min-w-0 items-center gap-1.5 text-[12px] text-[var(--color-ink-muted)]">
            <CaregiverAvatar reportedBy={event.reportedBy} size={15} />
            <span className="truncate">
              {event.reportedBy} &middot; {formatTimestamp(event.occurredAt)}
            </span>
            {event.evidence && <Mic size={10} className="shrink-0" aria-label="Has voice evidence" />}
          </span>
        </span>
        <span className="shrink-0">
          <StatusBadge status={event.status} size="sm" />
        </span>
      </button>
    </li>
  );
}
