import { useCareEvents } from "../state/CareEventsContext";
import { CareDetailLayout } from "../components/CareDetailLayout";
import { CareEventCard } from "../components/CareEventCard";
import { FilterBar } from "../components/FilterBar";
import { AllCaughtUp } from "../components/AllCaughtUp";
import { EmptyState } from "../components/EmptyState";
import { LeafOrnament } from "../components/LeafOrnament";
import { VoiceRecorder } from "../components/VoiceRecorder";
import { timeOfDayGreeting } from "../lib/greeting";
import { LAST_HANDOFF_LABEL } from "../lib/handoff";

export function CarePage() {
  const { visibleEvents, filter, setFilter, sortOrder, toggleSortOrder, selectedId, selectEvent } =
    useCareEvents();

  return (
    <CareDetailLayout>
      <div className="flex flex-col gap-8">
        <section className="relative overflow-hidden">
          <div className="flex items-start justify-between gap-6">
            <div className="min-w-0">
              <p className="text-[14px] font-medium text-[var(--color-ink-muted)]">
                {timeOfDayGreeting()}, Shivaansh
              </p>
              <h1 className="mt-1 font-display text-[32px] leading-[1.15] text-[var(--color-ink)] sm:text-[38px]">
                What changed since your last handoff?
              </h1>
              <p className="mt-2.5 max-w-lg text-[14.5px] leading-relaxed text-[var(--color-ink-soft)]">
                Here&rsquo;s what&rsquo;s new, what matters, and what might need your attention.
              </p>
              <div className="mt-4">
                <VoiceRecorder />
              </div>
            </div>

            <div className="relative hidden shrink-0 pt-2 sm:block">
              <LeafOrnament className="h-32 w-24 text-[var(--color-teal)]" />
              <p className="font-display absolute top-6 -left-28 w-32 rotate-[-3deg] text-right text-[13px] leading-snug text-[var(--color-ink-muted)] italic">
                &ldquo;Small updates make a big difference.&rdquo;
                <span className="mt-1 block text-[11px] not-italic">&mdash; ElderLink</span>
              </p>
            </div>
          </div>
        </section>

        <FilterBar
          filter={filter}
          onFilterChange={setFilter}
          sortOrder={sortOrder}
          onToggleSort={toggleSortOrder}
        />

        {visibleEvents.length === 0 ? (
          <EmptyState message="No updates match this filter yet." />
        ) : (
          <>
            <ul className="flex flex-col gap-2">
              {visibleEvents.map((event) => (
                <CareEventCard
                  key={event.id}
                  event={event}
                  selected={event.id === selectedId}
                  onSelect={() => selectEvent(event.id)}
                />
              ))}
            </ul>
            <AllCaughtUp since={LAST_HANDOFF_LABEL} />
          </>
        )}
      </div>
    </CareDetailLayout>
  );
}
