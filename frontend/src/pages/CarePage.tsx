import { Sun } from "lucide-react";
import clsx from "clsx";
import { useCareEvents } from "../state/CareEventsContext";
import { CareEventCard } from "../components/CareEventCard";
import { FilterBar } from "../components/FilterBar";
import { AllCaughtUp } from "../components/AllCaughtUp";
import { EmptyState } from "../components/EmptyState";
import { FamilyPhotoCard } from "../components/FamilyPhotoCard";
import { CareQuickActionsRail } from "../components/CareQuickActionsRail";
import { EventDetailDrawer } from "../components/EventDetailDrawer";
import { timeOfDayGreeting } from "../lib/greeting";
import { LAST_HANDOFF_LABEL } from "../lib/handoff";

export function CarePage() {
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

  return (
    <div
      className={clsx(
        "relative mx-auto max-w-[1400px] px-4 py-5 transition-[padding] duration-[280ms] ease-out sm:px-6 sm:py-7 lg:px-8 lg:py-9 xl:px-10",
        // Make room for the 26rem drawer so the page shifts left instead of sitting under it.
        selectedId && "lg:pr-[calc(26rem+2rem)] xl:pr-[calc(26rem+2.5rem)]",
      )}
    >
      <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:gap-8">
        <div className="min-w-0 flex-1">
          <section className="flex items-start justify-between gap-8">
            <div className="min-w-0 flex-1">
              <p className="flex items-center gap-1.5 text-[13.5px] font-medium text-[var(--color-ink-muted)] sm:text-[14.5px]">
                <Sun size={15} className="text-[var(--color-amber)]" aria-hidden="true" />
                {timeOfDayGreeting()}, Shivaansh <span aria-hidden="true">👋</span>
              </p>
              <h1 className="font-display mt-1.5 max-w-2xl text-[26px] leading-[1.12] font-medium tracking-[-0.01em] text-[var(--color-ink)] sm:text-[34px] lg:text-[42px]">
                What changed since your last handoff?
              </h1>
              <p className="mt-2.5 max-w-md text-[14px] leading-relaxed text-[var(--color-ink-soft)] sm:mt-3 sm:text-[15px]">
                Here&rsquo;s what&rsquo;s new, what matters, and what might need your attention.
              </p>
            </div>

            <div className="hidden w-40 shrink-0 flex-col items-end gap-2.5 pt-1 lg:flex">
              <p className="font-hand text-right text-[16px] leading-[1.15] text-[var(--color-ink-soft)]">
                &ldquo;Small updates create a safer, happier tomorrow.&rdquo;
              </p>
              <div className="flex items-end gap-1.5">
                <img
                  src="/assets/leaf-decoration.png"
                  alt=""
                  aria-hidden="true"
                  className="h-28 w-auto shrink-0 opacity-90"
                />
                <FamilyPhotoCard />
              </div>
            </div>
          </section>

          <div className="mt-5 sm:mt-6">
            <FilterBar
              filter={filter}
              onFilterChange={setFilter}
              sortOrder={sortOrder}
              onToggleSort={toggleSortOrder}
            />
          </div>

          <div className="mt-5 sm:mt-6">
            {isLoading ? (
              <EmptyState message="Loading care events..." />
            ) : error ? (
              <EmptyState message={`Couldn't load care events: ${error}`} />
            ) : visibleEvents.length === 0 ? (
              <EmptyState message="No updates match this filter yet." />
            ) : (
              <>
                <ul className="flex flex-col gap-2">
                  {visibleEvents.map((event) => (
                    <CareEventCard
                      key={event.id}
                      event={event}
                      selected={event.id === selectedId}
                      onSelect={() => toggleEvent(event.id)}
                    />
                  ))}
                </ul>
                <div className="mt-2">
                  <AllCaughtUp since={LAST_HANDOFF_LABEL} />
                </div>
              </>
            )}
          </div>
        </div>

        {/* Hidden (not unmounted, so an in-progress recording survives) while the detail panel is open. */}
        <CareQuickActionsRail className={selectedId ? "lg:hidden" : undefined} />
      </div>

      <EventDetailDrawer />
    </div>
  );
}
