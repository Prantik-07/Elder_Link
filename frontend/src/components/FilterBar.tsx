import { ArrowUpDown } from "lucide-react";
import clsx from "clsx";
import type { CareFilter, SortOrder } from "../state/CareEventsContext";

const FILTERS: { value: CareFilter; label: string }[] = [
  { value: "all", label: "All updates" },
  { value: "needs_verification", label: "Needs verification" },
  { value: "medication", label: "Medications" },
  { value: "observation", label: "Observations" },
  { value: "concern", label: "Concerns" },
];

export function FilterBar({
  filter,
  onFilterChange,
  sortOrder,
  onToggleSort,
}: {
  filter: CareFilter;
  onFilterChange: (f: CareFilter) => void;
  sortOrder: SortOrder;
  onToggleSort: () => void;
}) {
  return (
    <div
      role="group"
      aria-label="Filter care updates"
      className="flex flex-wrap items-center gap-2"
    >
      {FILTERS.map((f) => {
        const active = filter === f.value;
        return (
          <button
            key={f.value}
            type="button"
            aria-pressed={active}
            onClick={() => onFilterChange(f.value)}
            className={clsx(
              "rounded-full border px-3.5 py-1.5 text-[13px] font-medium transition-colors",
              active
                ? "border-transparent bg-[var(--color-teal)] text-[var(--color-paper)]"
                : "border-[var(--color-line)] bg-[var(--color-paper)] text-[var(--color-ink-soft)] hover:border-[var(--color-teal)]/40 hover:text-[var(--color-ink)]",
            )}
          >
            {f.value === "needs_verification" && !active && (
              <span
                className="mr-1.5 inline-block h-1.5 w-1.5 rounded-full align-middle"
                style={{ backgroundColor: "var(--color-amber)" }}
                aria-hidden="true"
              />
            )}
            {f.label}
          </button>
        );
      })}

      <button
        type="button"
        onClick={onToggleSort}
        className="ml-auto flex items-center gap-1.5 rounded-full border border-[var(--color-line)] bg-[var(--color-paper)] px-3.5 py-1.5 text-[13px] font-medium text-[var(--color-ink-soft)] transition-colors hover:text-[var(--color-ink)]"
      >
        <ArrowUpDown size={13} aria-hidden="true" />
        {sortOrder === "recent" ? "Most recent" : "Oldest first"}
      </button>
    </div>
  );
}
