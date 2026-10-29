import React from "react";
import ReactDOM from "react-dom/client";
import "./fonts.css";
import App from "./App";
import "./styles.css";
import "./workspace.css";
import "./pages/radar-workspace.css";

class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <main className="fatal">
        <h1>Precisamos recarregar a interface.</h1>
        <p>Seus dados salvos continuam no servidor.</p>
        <button onClick={() => location.reload()}>Recarregar</button>
      </main>
    ) : (
      this.props.children
    );
  }
}
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
);
