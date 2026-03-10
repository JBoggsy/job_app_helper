import { useState, useEffect, lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import NavigationBar from "./components/NavigationBar";
import ChatPanel from "./components/ChatPanel";
import UpdateBanner from "./components/UpdateBanner";
import SetupWizard from "./components/SetupWizard";
import { ToastContainer } from "./components/Toast";
import { useAppContext } from "./contexts/AppContext";
import { fetchOnboardingStatus, fetchHealth } from "./api";

import HomePage from "./pages/HomePage";
import JobTrackerPage from "./pages/JobTrackerPage";
import JobDetailPage from "./pages/JobDetailPage";
const DocumentEditorPage = lazy(() => import("./pages/DocumentEditorPage"));
import SettingsPage from "./pages/SettingsPage";
import ProfilePage from "./pages/ProfilePage";
import HelpPage from "./pages/HelpPage";

function App() {
  const {
    chatOpen, setChatOpen,
    onboarding, setOnboarding,
    bumpJobsVersion,
    toasts, removeToast,
    handleChatError,
  } = useAppContext();

  const [onboardingChecked, setOnboardingChecked] = useState(false);
  const [pendingOnboarding, setPendingOnboarding] = useState(false);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [updateInfo, setUpdateInfo] = useState(null);

  // In Tauri, intercept external link clicks and open in system browser
  useEffect(() => {
    if (!window.__TAURI_INTERNALS__) return;
    function handleClick(e) {
      const anchor = e.target.closest("a[href]");
      if (!anchor) return;
      const href = anchor.getAttribute("href");
      if (!href || href.startsWith("#") || href.startsWith("javascript:")) return;
      if (/^(https?:|mailto:)/i.test(href)) {
        e.preventDefault();
        import("@tauri-apps/plugin-shell").then(({ open }) => open(href));
      }
    }
    document.addEventListener("click", handleClick, true);
    return () => document.removeEventListener("click", handleClick, true);
  }, []);

  // Check for app updates in Tauri
  useEffect(() => {
    if (!window.__TAURI_INTERNALS__) return;
    import("@tauri-apps/plugin-updater").then(({ check }) => {
      check().then((update) => {
        if (update) setUpdateInfo(update);
      }).catch((err) => console.error("Update check failed:", err));
    });
  }, []);

  useEffect(() => {
    checkHealthAndOnboarding();
  }, []);

  async function checkHealthAndOnboarding() {
    try {
      const health = await fetchHealth();
      const llmConfigured = health.llm?.configured || false;

      if (!llmConfigured) {
        const { onboarded, onboarding_state } = await fetchOnboardingStatus();
        if (!onboarded || onboarding_state === "in_progress") {
          setPendingOnboarding(true);
          setWizardOpen(true);
        }
      } else {
        const { onboarded, onboarding_state } = await fetchOnboardingStatus();
        if (!onboarded || onboarding_state === "in_progress") {
          setOnboarding(true);
          setChatOpen(true);
        }
      }
    } catch (e) {
      console.error("Failed to check health and onboarding status:", e);
    } finally {
      setOnboardingChecked(true);
    }
  }

  async function handleSettingsSaved() {
    if (pendingOnboarding) {
      setPendingOnboarding(false);
      setOnboarding(true);
      setChatOpen(true);
    }
  }

  function handleWizardComplete() {
    setWizardOpen(false);
    setPendingOnboarding(false);
    setOnboarding(true);
    setChatOpen(true);
  }

  function handleWizardClose() {
    setWizardOpen(false);
  }

  function handleOnboardingComplete() {
    setOnboarding(false);
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {updateInfo && (
        <UpdateBanner update={updateInfo} onDismiss={() => setUpdateInfo(null)} />
      )}
      <NavigationBar />
      <main className="max-w-6xl mx-auto px-4 py-8">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/jobs" element={<JobTrackerPage />} />
          <Route path="/jobs/:id" element={<JobDetailPage />} />
          <Route path="/jobs/:id/documents/:type" element={
            <Suspense fallback={<div className="flex items-center justify-center h-64"><span className="inline-block w-6 h-6 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" /></div>}>
              <DocumentEditorPage />
            </Suspense>
          } />
          <Route path="/settings" element={<SettingsPage onSaved={handleSettingsSaved} />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/help" element={<HelpPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <ChatPanel
        isOpen={chatOpen}
        onClose={() => setChatOpen(false)}
        onboarding={onboarding}
        onOnboardingComplete={handleOnboardingComplete}
        onJobsChanged={bumpJobsVersion}
        onError={handleChatError}
      />
      <SetupWizard
        isOpen={wizardOpen}
        onClose={handleWizardClose}
        onComplete={handleWizardComplete}
      />
      <ToastContainer toasts={toasts} onDismiss={removeToast} />
    </div>
  );
}

export default App;
