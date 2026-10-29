import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import "./index.css";
import { AppProvider, useApp } from "./store";
import { Layout } from "./components/Layout";
import { QuickAdd } from "./components/QuickAdd";
import { ApplicationDrawer, SavedDrawer } from "./components/ApplicationDrawer";
import Overview from "./pages/Overview";
import Applications from "./pages/Applications";
import Analytics from "./pages/Analytics";
import Settings from "./pages/Settings";
import Career from "./pages/Career";
import Me from "./pages/Me";

/** Discover was folded into Quick add: old links open it. */
function DiscoverRedirect() {
  const { setQuickAdd } = useApp();
  React.useEffect(() => { setQuickAdd(true); }, []);
  return <Navigate to="/applications" replace />;
}

function Overlays() {
  const { openAppId, openApp, openSavedId, openSaved } = useApp();
  return (
    <>
      <QuickAdd />
      <ApplicationDrawer id={openAppId} onClose={() => openApp(null)} />
      <SavedDrawer id={openSavedId} onClose={() => openSaved(null)} />
    </>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AppProvider>
        <Layout>
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/applications" element={<Applications />} />
            <Route path="/discover" element={<DiscoverRedirect />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/career" element={<Career />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/me" element={<Me />} />
            <Route path="*" element={<Overview />} />
          </Routes>
        </Layout>
        <Overlays />
      </AppProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
