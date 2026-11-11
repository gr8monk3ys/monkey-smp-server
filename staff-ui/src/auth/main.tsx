import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "../styles/app.css";
import "./auth.css";
import { AuthPage } from "./Pages";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AuthPage />
  </StrictMode>,
);
