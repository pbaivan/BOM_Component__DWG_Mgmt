import React from 'react';

export class AppErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      message: '',
    };
  }

  static getDerivedStateFromError(error) {
    return {
      hasError: true,
      message: String(error?.message || 'Unknown render error'),
    };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Unhandled React render error:', error, errorInfo);
  }

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    return (
      <div className="min-h-screen bg-slate-100 flex items-center justify-center px-6">
        <div className="max-w-xl w-full rounded-xl border border-rose-200 bg-white p-6 shadow-lg">
          <h1 className="text-xl font-bold text-rose-700">Application Error</h1>
          <p className="mt-2 text-sm text-slate-700">
            The page encountered an unexpected UI error. You can reload the page and retry your operation.
          </p>
          <p className="mt-3 rounded bg-slate-50 border border-slate-200 p-2 text-xs text-slate-600 break-words">
            {this.state.message}
          </p>
          <div className="mt-4">
            <button
              type="button"
              onClick={this.handleReload}
              className="px-4 py-2 rounded bg-rose-600 text-white text-sm font-semibold hover:bg-rose-700 transition"
            >
              Reload Application
            </button>
          </div>
        </div>
      </div>
    );
  }
}
