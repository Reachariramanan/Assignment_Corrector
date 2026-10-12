import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Render error caught by ErrorBoundary:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="max-w-2xl mx-auto mt-16 p-6 rounded-xl border text-sm" style={{ borderColor: "var(--dsa-border)", background: "var(--dsa-surface)" }}>
          <h2 className="font-semibold mb-2">Something went wrong rendering this view</h2>
          <p style={{ color: "var(--dsa-muted)" }} className="mb-3">
            {this.state.error.message}
          </p>
          <button
            className="rounded-md px-3 py-1.5 text-sm"
            style={{ background: "var(--dsa-accent)", color: "var(--dsa-bg)" }}
            onClick={() => {
              this.setState({ error: null });
              window.location.hash = "#/";
            }}
          >
            Back to Dashboard
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
