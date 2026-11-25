import { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
  onReset?: () => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught rendering error:', error, errorInfo);
    this.setState({ errorInfo });
  }

  public handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-full w-full flex-col items-center justify-center p-6 bg-[#0B0F17] text-white">
          <div className="max-w-md w-full rounded-lg border border-red-500/30 bg-[#121824] p-5 shadow-xl text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-500/10 text-red-500 mb-3">
              <AlertTriangle className="h-6 w-6" />
            </div>
            <h3 className="font-mono text-sm font-bold uppercase tracking-wider text-red-400">
              {this.props.fallbackTitle || 'Telemetry Stage Render Error'}
            </h3>
            <p className="mt-2 text-xs text-[#94A3B8] font-sans">
              An unexpected render error occurred in the visualization stage. Chat and historical queries remain operational.
            </p>
            {this.state.error && (
              <pre className="mt-3 max-h-32 overflow-auto rounded bg-[#0B0F17] p-2 text-left font-mono text-[11px] text-red-300/80 border border-red-900/40">
                {this.state.error.message || String(this.state.error)}
              </pre>
            )}
            <button
              onClick={this.handleReset}
              className="mt-4 inline-flex items-center space-x-2 rounded bg-red-600/20 px-4 py-2 font-mono text-xs font-semibold text-red-300 border border-red-500/30 hover:bg-red-600/30 transition-colors"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              <span>Reset Visualization Stage</span>
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
