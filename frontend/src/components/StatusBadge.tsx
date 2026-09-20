import { Check, CircleHelp, TriangleAlert } from "lucide-react";
import type { CareEventStatus } from "../data/types";

const STATUS_META: Record<
  CareEventStatus,
  { label: string; icon: typeof Check; fg: string; bg: string; border: string }
> = {
  verified: {
    label: "Verified",
    icon: Check,
    fg: "var(--color-verified)",
    bg: "var(--color-verified-soft)",
    border: "var(--color-verified-line)",
  },
  needs_verification: {
    label: "Needs verification",
    icon: TriangleAlert,
    fg: "var(--color-amber)",
    bg: "var(--color-amber-soft)",
    border: "var(--color-amber-line)",
  },
  uncertain: {
    label: "Uncertain",
    icon: CircleHelp,
    fg: "var(--color-uncertain)",
    bg: "var(--color-uncertain-soft)",
    border: "var(--color-uncertain-line)",
  },
};

export function StatusBadge({
  status,
  size = "md",
}: {
  status: CareEventStatus;
  size?: "sm" | "md";
}) {
  const meta = STATUS_META[status];
  const Icon = meta.icon;
  const padding = size === "sm" ? "px-2 py-0.5 text-[12px]" : "px-2.5 py-1 text-xs";

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border font-medium whitespace-nowrap ${padding}`}
      style={{
        color: meta.fg,
        backgroundColor: meta.bg,
        borderColor: meta.border,
      }}
    >
      <Icon size={size === "sm" ? 11 : 12.5} strokeWidth={2.5} aria-hidden="true" />
      {meta.label}
    </span>
  );
}

export { STATUS_META };
