import { useMemo } from "react";
import { useCareEvents } from "../state/CareEventsContext";
import { CareDetailLayout } from "../components/CareDetailLayout";
import { FilterBar } from "../components/FilterBar";
import { EmptyState } from "../components/EmptyState";
import { TimelineEvent } from "../components/TimelineEvent";
import { relativeDayLabel } from "../lib/format";
import type { CareEvent } from "../data/types";

function groupByDay(events: CareEvent[]): { label: string; items: CareEvent[] }[] {
  const groups: { label: string; items: CareEvent[] }[] = [];
  for (const event of events) {
    const label = relativeDayLabel(event.occurredAt);
    const existing = groups.find((g) => g.label === label);
    if (existing) existing.items.push(event);
    else groups.push({ label, items: [event] });
  }
  return groups;
}

export function TimelinePage() {
  const {
    visibleEvents,
    isLoading,
    error,
    filter,
    setFilter,
    sortOrder,
    toggleSortOrder,
    selectedId,
    toggleEvent,
  } = useCareEvents();

  const groups = useMemo(() => groupByDay(visibleEvents), [visibleEvents]);

  return (
    <CareDetailLayout>
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="font-display text-[28px] text-[var(--color-ink)]">Timeline</h1>
          <p className="mt-1.5 text-[14px] text-[var(--color-ink-soft)]">
            A longitudinal record of care - every change, who reported it, and the evidence behind it.
          </p>
        </div>

        <FilterBar
          filter={filter}
          onFilterChange={setFilter}
          sortOrder={sortOrder}
          onToggleSort={toggleSortOrder}
        />

        {isLoading ? (
          <EmptyState message="Loading care events..." />
        ) : error ? (
          <EmptyState message={`Couldn't load care events: ${error}`} />
        ) : groups.length === 0 ? (
          <EmptyState message="No updates match this filter yet." />
        ) : (
          <div className="flex flex-col gap-7">
            {groups.map((group) => (
              <section key={group.label}>
                <h2 className="mb-2 text-[13px] font-semibold tracking-wide text-[var(--color-ink-muted)] uppercase">
                  {group.label}
                </h2>
                <ul>
                  {group.items.map((event, i) => (
                    <TimelineEvent
                      key={event.id}
                      event={event}
                      selected={event.id === selectedId}
                      isLast={i === group.items.length - 1}
                      onSelect={() => toggleEvent(event.id)}
                    />
                  ))}
                </ul>
              </section>
            ))}
          </div>
        )}
      </div>
    </CareDetailLayout>
  );
}
