import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallbackTitle?: string;
}

interface ErrorBoundaryState {
  errorMessage: string | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = {
    errorMessage: null,
  };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return {
      errorMessage: error.message,
    };
  }

  componentDidCatch(_error: Error, _errorInfo: ErrorInfo) {}

  render() {
    if (this.state.errorMessage) {
      return (
        <div
          role="alert"
          style={{
            border: "1px solid #fda29b",
            borderRadius: 18,
            padding: 20,
            background: "#fef3f2",
            color: "#b42318",
          }}
        >
          <strong>{this.props.fallbackTitle ?? "页面加载失败"}</strong>
          <p style={{ marginBottom: 0 }}>{this.state.errorMessage}</p>
        </div>
      );
    }

    return this.props.children;
  }
}
