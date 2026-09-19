import { Route, Routes } from "react-router-dom";
import { Header } from "./components/Header";
import { BottomNav } from "./components/BottomNav";
import { CarePage } from "./pages/CarePage";
import { TimelinePage } from "./pages/TimelinePage";
import { HandoffPage } from "./pages/HandoffPage";
import { CareCirclePage } from "./pages/CareCirclePage";
import { CareEventsProvider } from "./state/CareEventsContext";

export default function App() {
  return (
    <CareEventsProvider>
      <div className="min-h-screen bg-[var(--color-ivory)]">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-full focus:bg-[var(--color-teal)] focus:px-4 focus:py-2 focus:text-[var(--color-paper)]"
        >
          Skip to content
        </a>
        <Header />
        {/* Bottom nav is fixed and phone/tablet-only (lg:hidden) - this
            padding keeps it from covering the last card of any page. */}
        <main id="main-content" className="pb-[calc(4.5rem+env(safe-area-inset-bottom))] lg:pb-0">
          <Routes>
            <Route path="/" element={<CarePage />} />
            <Route path="/timeline" element={<TimelinePage />} />
            <Route path="/handoff" element={<HandoffPage />} />
            <Route path="/care-circle" element={<CareCirclePage />} />
          </Routes>
        </main>
        <BottomNav />
      </div>
    </CareEventsProvider>
  );
}
