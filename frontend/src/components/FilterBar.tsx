import { ChevronDown } from "lucide-react";
import clsx from "clsx";
import type { CareFilter, SortOrder } from "../state/CareEventsContext";

const FILTERS: { value: CareFilter; label: string }[] = [
  { value: "all", label: "All updates" },
  { value: "needs_verification", label: "Needs attention" },
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
      className="flex flex-wrap items-center gap-2 lg:flex-nowrap lg:gap-2"
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
              "shrink-0 rounded-full border px-3.5 py-1.5 text-[13px] font-medium whitespace-nowrap transition-colors",
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
        className="ml-auto flex shrink-0 items-center gap-1 rounded-full px-2 py-1.5 text-[13px] font-medium whitespace-nowrap text-[var(--color-ink-soft)] transition-colors hover:text-[var(--color-ink)]"
      >
        Sort: {sortOrder === "recent" ? "Latest" : "Oldest"}
        <ChevronDown size={14} aria-hidden="true" />
      </button>
    </div>
  );
}
