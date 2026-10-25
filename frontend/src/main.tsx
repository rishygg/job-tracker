import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "./index.css";
import { AppProvider, useApp } from "./store";
import { Layout } from "./components/Layout";
import { QuickAdd } from "./components/QuickAdd";
import { ApplicationDrawer } from "./components/ApplicationDrawer";
import Overview from "./pages/Overview";
import Applications from "./pages/Applications";
import Analytics from "./pages/Analytics";
import Settings from "./pages/Settings";
import { CareerPlaceholder, DiscoverPlaceholder } from "./pages/Placeholders";

function Overlays() {
  const { openAppId, openApp } = useApp();
  return (
    <>
      <QuickAdd />
      <ApplicationDrawer id={openAppId} onClose={() => openApp(null)} />
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
            <Route path="/discover" element={<DiscoverPlaceholder />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/career" element={<CareerPlaceholder />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Overview />} />
          </Routes>
        </Layout>
        <Overlays />
      </AppProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
