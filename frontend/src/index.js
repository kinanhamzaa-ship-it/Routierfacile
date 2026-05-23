import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

// PWA: register service worker after the page has loaded so it never blocks
// the first paint. Only runs over https (or localhost).
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/service-worker.js")
      .catch(() => {
        /* swallow: SW is a progressive enhancement */
      });
  });
}
