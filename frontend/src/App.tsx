import { useEffect, useState } from "react";
import { AnimatePresence } from "framer-motion";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Header } from "./components/Header";
import { BottomNav } from "./components/BottomNav";
import { CarePage } from "./pages/CarePage";
import { TimelinePage } from "./pages/TimelinePage";
import { HandoffPage } from "./pages/HandoffPage";
import { CareCirclePage } from "./pages/CareCirclePage";
import { SplashScreen } from "./components/SplashScreen";
import { CareEventsProvider, useCareEvents } from "./state/CareEventsContext";
import { PatientsProvider, usePatients } from "./state/PatientsContext";

/** Selection is shared state, so drop it on navigation instead of opening the panel on the next page. */
function ClearSelectionOnNavigate() {
  const { pathname } = useLocation();
  const { selectEvent } = useCareEvents();
  const patientId = usePatients().activePatient?.id;
  useEffect(() => {
    selectEvent(null);
  }, [pathname, patientId, selectEvent]);
  return null;
}

const SPLASH_MS = 3800;

export default function App() {
  const [showSplash, setShowSplash] = useState(true);
  useEffect(() => {
    const t = setTimeout(() => setShowSplash(false), SPLASH_MS);
    return () => clearTimeout(t);
  }, []);

  return (
    <PatientsProvider>
    <CareEventsProvider>
      <AnimatePresence>{showSplash && <SplashScreen />}</AnimatePresence>
      <ClearSelectionOnNavigate />
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
            {/* Unknown or removed URLs (e.g. the old /patients) land on Home instead of a blank page. */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
        <BottomNav />
      </div>
    </CareEventsProvider>
    </PatientsProvider>
  );
}
