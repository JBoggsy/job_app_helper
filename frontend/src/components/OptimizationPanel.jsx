import { useState, useEffect, useCallback } from "react";
import useResizablePanel from "../hooks/useResizablePanel";
import { fetchOptimizationStatus, runOptimization } from "../api";

export default function OptimizationPanel({ isOpen, onClose }) {
  const { width, isDragging, handleMouseDown } = useResizablePanel("optimizationPanelWidth", 520);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [optimizing, setOptimizing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const loadStatus = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchOptimizationStatus();
      setStatus(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      loadStatus();
      setResult(null);
    }
  }, [isOpen, loadStatus]);

  async function handleOptimize() {
    setOptimizing(true);
    setResult(null);
    setError(null);
    try {
      const data = await runOptimization();
      setResult(data);
      // Refresh status after optimization
      await loadStatus();
    } catch (e) {
      setError(e.message);
    } finally {
      setOptimizing(false);
    }
  }

  if (!isOpen) return null;

  const anyReady = status?.some((m) => m.ready);
  const totalScored = status?.reduce((sum, m) => sum + m.scored_count, 0) || 0;
  const totalUnscored = status?.reduce((sum, m) => sum + m.unscored_count, 0) || 0;

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/30 z-40" onClick={onClose} />

      {/* Panel */}
      <div
        className={`fixed right-0 top-0 h-full bg-white shadow-xl z-50 flex flex-col${isDragging ? " select-none" : ""}`}
        style={{ width }}
      >
        {/* Resize handle */}
        <div
          onMouseDown={handleMouseDown}
          className="absolute left-0 top-0 h-full w-1.5 cursor-col-resize hover:bg-blue-400/40 active:bg-blue-400/60 z-10 transition-colors"
        />

        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b bg-gray-50">
          <h2 className="font-semibold text-gray-900">AI Optimization</h2>
          <button onClick={onClose} className="p-1 text-gray-500 hover:text-gray-700">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">

          {/* Intro */}
          <section>
            <p className="text-sm text-gray-600">
              The AI learns from your behavior to improve job evaluations and search queries.
              As you use the app, training examples are collected automatically. Once enough
              data accumulates, you can optimize the AI modules below.
            </p>
          </section>

          {/* How it works */}
          <section>
            <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">How It Works</h3>
            <ol className="space-y-2 text-sm text-gray-600">
              <li className="flex gap-2">
                <span className="flex-shrink-0 w-5 h-5 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-xs font-semibold">1</span>
                <span><strong>Search for jobs</strong> using the AI assistant</span>
              </li>
              <li className="flex gap-2">
                <span className="flex-shrink-0 w-5 h-5 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-xs font-semibold">2</span>
                <span><strong>Add results</strong> you like to your tracker</span>
              </li>
              <li className="flex gap-2">
                <span className="flex-shrink-0 w-5 h-5 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-xs font-semibold">3</span>
                <span><strong>Edit fit ratings</strong> on tracked jobs if the AI got them wrong</span>
              </li>
              <li className="flex gap-2">
                <span className="flex-shrink-0 w-5 h-5 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-xs font-semibold">4</span>
                <span><strong>Optimize</strong> once you have enough scored examples</span>
              </li>
            </ol>
          </section>

          {/* Module status */}
          <section>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Module Status</h3>
              <button
                onClick={loadStatus}
                disabled={loading}
                className="text-xs text-blue-600 hover:text-blue-800 disabled:text-gray-400"
              >
                {loading ? "Refreshing..." : "Refresh"}
              </button>
            </div>

            {error && !status && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                {error}
              </div>
            )}

            {loading && !status && (
              <div className="text-sm text-gray-500">Loading status...</div>
            )}

            {status && (
              <div className="space-y-3">
                {status.map((mod) => (
                  <ModuleCard key={mod.module_name} module={mod} />
                ))}
              </div>
            )}
          </section>

          {/* Summary stats */}
          {status && (
            <section>
              <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">Training Data</h3>
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 bg-gray-50 rounded-lg text-center">
                  <div className="text-2xl font-bold text-gray-900">{totalScored}</div>
                  <div className="text-xs text-gray-500 mt-0.5">Scored examples</div>
                </div>
                <div className="p-3 bg-gray-50 rounded-lg text-center">
                  <div className="text-2xl font-bold text-gray-900">{totalUnscored}</div>
                  <div className="text-xs text-gray-500 mt-0.5">Awaiting feedback</div>
                </div>
              </div>
            </section>
          )}

          {/* Optimize button */}
          {status && (
            <section>
              <button
                onClick={handleOptimize}
                disabled={!anyReady || optimizing}
                className={`w-full py-3 px-4 rounded-lg font-medium text-sm flex items-center justify-center gap-2 ${
                  anyReady && !optimizing
                    ? "bg-blue-600 text-white hover:bg-blue-700"
                    : "bg-gray-100 text-gray-400 cursor-not-allowed"
                }`}
              >
                {optimizing ? (
                  <>
                    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Optimizing...
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    {anyReady ? "Run Optimization" : "Not enough data yet"}
                  </>
                )}
              </button>
              {!anyReady && status.length > 0 && (
                <p className="text-xs text-gray-500 mt-2 text-center">
                  Need at least {status[0]?.min_required || 10} scored examples per module.
                  Keep searching for jobs and adding results to your tracker.
                </p>
              )}
            </section>
          )}

          {/* Optimization result */}
          {result && (
            <section>
              <div className={`p-4 rounded-lg border ${
                result.modules_optimized?.length > 0
                  ? "bg-green-50 border-green-200"
                  : "bg-yellow-50 border-yellow-200"
              }`}>
                <h4 className={`font-medium text-sm ${
                  result.modules_optimized?.length > 0 ? "text-green-800" : "text-yellow-800"
                }`}>
                  {result.modules_optimized?.length > 0
                    ? "Optimization Complete"
                    : "No Modules Optimized"
                  }
                </h4>
                {result.modules_optimized?.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {result.modules_optimized.map((name) => (
                      <div key={name} className="text-sm text-green-700 flex items-center gap-1.5">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                        <span className="capitalize">{name.replace("_", " ")}</span>
                        {result.examples_used?.[name] && (
                          <span className="text-green-600">({result.examples_used[name]} examples)</span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
                {result.errors && Object.keys(result.errors).length > 0 && (
                  <div className="mt-2 space-y-1">
                    {Object.entries(result.errors).map(([name, err]) => (
                      <div key={name} className="text-sm text-yellow-700">
                        <span className="capitalize">{name.replace("_", " ")}</span>: {err}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </section>
          )}

          {/* Error display */}
          {error && status && (
            <section>
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                {error}
              </div>
            </section>
          )}
        </div>
      </div>
    </>
  );
}


function ModuleCard({ module: mod }) {
  const progress = mod.min_required > 0
    ? Math.min(100, Math.round((mod.scored_count / mod.min_required) * 100))
    : 0;

  const displayName = mod.module_name === "evaluator"
    ? "Job Evaluator"
    : mod.module_name === "query_generator"
      ? "Query Generator"
      : mod.module_name.replace("_", " ");

  const description = mod.module_name === "evaluator"
    ? "Rates how well jobs match your profile"
    : mod.module_name === "query_generator"
      ? "Creates optimized search queries"
      : "";

  return (
    <div className="border rounded-lg p-3">
      <div className="flex items-center justify-between mb-1">
        <div>
          <span className="font-medium text-sm text-gray-900">{displayName}</span>
          {description && (
            <p className="text-xs text-gray-500">{description}</p>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          {mod.has_optimized_module && (
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
              Optimized
            </span>
          )}
          {mod.ready ? (
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
              Ready
            </span>
          ) : (
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
              Collecting
            </span>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div className="mt-2">
        <div className="flex justify-between text-xs text-gray-500 mb-1">
          <span>{mod.scored_count} / {mod.min_required} scored examples</span>
          <span>{progress}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-1.5">
          <div
            className={`h-1.5 rounded-full transition-all ${
              mod.ready ? "bg-blue-500" : "bg-gray-400"
            }`}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {mod.last_optimized && (
        <div className="text-xs text-gray-400 mt-1.5">
          Last optimized: {new Date(mod.last_optimized).toLocaleDateString()}
        </div>
      )}
    </div>
  );
}
