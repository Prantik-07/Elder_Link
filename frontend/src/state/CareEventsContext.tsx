import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { fetchCareEventTimeline, USE_MOCK_DATA } from "../data/api";
import { mockCareEvents } from "../data/mockEvents";
import type { CareEvent, CareEventStatus } from "../data/types";

export type CareFilter =
  | "all"
  | "needs_verification"
  | "medication"
  | "observation"
  | "concern";

export type SortOrder = "recent" | "oldest";

interface CareEventsContextValue {
  events: CareEvent[];
  isLoading: boolean;
  error: string | null;
  filter: CareFilter;
  setFilter: (filter: CareFilter) => void;
  sortOrder: SortOrder;
  toggleSortOrder: () => void;
  search: string;
  setSearch: (value: string) => void;
  visibleEvents: CareEvent[];
  selectedId: string | null;
  selectEvent: (id: string | null) => void;
  toggleEvent: (id: string) => void;
  selectedEvent: CareEvent | null;
  setStatus: (id: string, status: CareEventStatus) => void;
  addEvent: (event: CareEvent) => void;
}

const CareEventsContext = createContext<CareEventsContextValue | null>(null);

export function CareEventsProvider({ children }: { children: ReactNode }) {
  const [events, setEvents] = useState<CareEvent[]>(USE_MOCK_DATA ? mockCareEvents : []);
  const [isLoading, setIsLoading] = useState(!USE_MOCK_DATA);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<CareFilter>("all");
  const [sortOrder, setSortOrder] = useState<SortOrder>("recent");
  const [search, setSearch] = useState("");
  // No event is selected by default: on mobile/tablet the detail view is a
  // full-screen overlay, so auto-selecting one on load would trap the user
  // behind it before they ever see the list.
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // The context is the single event source for the whole app (Care
  // Overview, Timeline, Handoff all read from it) - fetching here, once,
  // is what keeps every page from independently requesting the same
  // timeline and racing/duplicating requests.
  useEffect(() => {
    if (USE_MOCK_DATA) return;

    let cancelled = false;
    setIsLoading(true);
    setError(null);

    fetchCareEventTimeline()
      .then((fetched) => {
        if (cancelled) return;
        setEvents(fetched);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        // A real API/backend failure must be visible, not silently
        // swallowed into an empty or mock timeline - an empty list here
        // would be indistinguishable from a legitimately empty timeline.
        setError(err instanceof Error ? err.message : "Failed to load care events.");
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const setStatus = useCallback((id: string, status: CareEventStatus) => {
    setEvents((prev) => prev.map((e) => (e.id === id ? { ...e, status } : e)));
  }, []);

  const addEvent = useCallback((event: CareEvent) => {
    setEvents((prev) => [event, ...prev]);
    setSelectedId(event.id);
  }, []);

  const selectEvent = useCallback((id: string | null) => setSelectedId(id), []);
  const toggleEvent = useCallback(
    (id: string) => setSelectedId((prev) => (prev === id ? null : id)),
    [],
  );

  const toggleSortOrder = useCallback(() => {
    setSortOrder((prev) => (prev === "recent" ? "oldest" : "recent"));
  }, []);

  const visibleEvents = useMemo(() => {
    let list = [...events];

    if (filter === "needs_verification") {
      list = list.filter((e) => e.status === "needs_verification" || e.status === "uncertain");
    } else if (filter !== "all") {
      list = list.filter((e) => e.type === filter);
    }

    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter(
        (e) =>
          e.title.toLowerCase().includes(q) ||
          e.summary.toLowerCase().includes(q) ||
          e.reportedBy.toLowerCase().includes(q) ||
          (e.categoryLabel ?? "").toLowerCase().includes(q),
      );
    }

    list.sort((a, b) => {
      const diff = new Date(b.occurredAt).getTime() - new Date(a.occurredAt).getTime();
      return sortOrder === "recent" ? diff : -diff;
    });

    return list;
  }, [events, filter, search, sortOrder]);

  const selectedEvent = useMemo(
    () => events.find((e) => e.id === selectedId) ?? null,
    [events, selectedId],
  );

  const value: CareEventsContextValue = {
    events,
    isLoading,
    error,
    filter,
    setFilter,
    sortOrder,
    toggleSortOrder,
    search,
    setSearch,
    visibleEvents,
    selectedId,
    selectEvent,
    toggleEvent,
    selectedEvent,
    setStatus,
    addEvent,
  };

  return <CareEventsContext.Provider value={value}>{children}</CareEventsContext.Provider>;
}

export function useCareEvents(): CareEventsContextValue {
  const ctx = useContext(CareEventsContext);
  if (!ctx) throw new Error("useCareEvents must be used within CareEventsProvider");
  return ctx;
}
