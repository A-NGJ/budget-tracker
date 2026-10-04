import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";

// Legacy read-only stats dashboard over the plaintext FastAPI backend, kept
// for existing local data until history is re-imported. It is a separate
// page (stats.html) so the encrypted workspace bundle never calls /api.
ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
