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
      className="flex flex-col gap-2 lg:flex-row lg:flex-wrap lg:items-center xl:flex-nowrap"
    >
      {/* Below lg, chips scroll horizontally in their own strip instead of
          wrapping to several rows or overflowing the page - the scrollbar
          stays contained to this control. */}
      <div className="thin-scroll -mx-4 flex items-center gap-2 overflow-x-auto px-4 pb-1 sm:-mx-6 sm:px-6 lg:mx-0 lg:overflow-visible lg:px-0 lg:pb-0">
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
      </div>

      <button
        type="button"
        onClick={onToggleSort}
        className="flex shrink-0 items-center gap-1 self-end rounded-full px-2 py-1.5 text-[13px] font-medium whitespace-nowrap text-[var(--color-ink-soft)] transition-colors hover:text-[var(--color-ink)] lg:ml-auto lg:self-auto"
      >
        Sort: {sortOrder === "recent" ? "Latest" : "Oldest"}
        <ChevronDown size={14} aria-hidden="true" />
      </button>
    </div>
  );
}
