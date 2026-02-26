import { useState } from "react";

function StarRating({ rating }) {
  return (
    <span className="inline-flex gap-0.5" title={`${rating}/5 fit`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <svg
          key={i}
          className={`w-4 h-4 ${i <= rating ? "text-yellow-400" : "text-gray-300"}`}
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.286 3.957a1 1 0 00.95.69h4.162c.969 0 1.371 1.24.588 1.81l-3.37 2.448a1 1 0 00-.364 1.118l1.287 3.957c.3.921-.755 1.688-1.54 1.118l-3.37-2.448a1 1 0 00-1.176 0l-3.37 2.448c-.784.57-1.838-.197-1.539-1.118l1.287-3.957a1 1 0 00-.364-1.118L2.063 9.384c-.783-.57-.38-1.81.588-1.81h4.162a1 1 0 00.95-.69l1.286-3.957z" />
        </svg>
      ))}
    </span>
  );
}

function ResultCard({ result, onAddToTracker }) {
  const [expanded, setExpanded] = useState(false);
  const [adding, setAdding] = useState(false);
  const [addPhase, setAddPhase] = useState(""); // "", "enriching", "done"

  const handleAdd = async (e) => {
    e.stopPropagation();
    setAdding(true);
    setAddPhase("enriching");
    try {
      await onAddToTracker(result.id);
      setAddPhase("done");
    } catch {
      setAdding(false);
      setAddPhase("");
    }
  };

  const addButtonLabel = addPhase === "enriching" ? "Enriching & Adding..." : "Add to Tracker";

  const salary =
    result.salary_min || result.salary_max
      ? [
          result.salary_min ? `$${(result.salary_min / 1000).toFixed(0)}k` : null,
          result.salary_max ? `$${(result.salary_max / 1000).toFixed(0)}k` : null,
        ]
          .filter(Boolean)
          .join("–")
      : null;

  const meta = [result.location, result.remote_type, salary].filter(Boolean).join(" · ");

  return (
    <div
      className={`border rounded-lg transition-all cursor-pointer ${
        expanded ? "bg-white shadow-sm" : "bg-gray-50 hover:bg-white"
      } ${result._isNew ? "animate-slide-in" : ""}`}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="px-3 py-2.5">
        <div className="flex items-start gap-2">
          <StarRating rating={result.job_fit || 0} />
          <div className="flex-1 min-w-0">
            <p className="font-medium text-sm text-gray-900 truncate">
              {result.title}
            </p>
            <p className="text-xs text-gray-600 truncate">{result.company}</p>
          </div>
          {result.added_to_tracker && (
            <span className="text-xs text-green-600 font-medium whitespace-nowrap flex items-center gap-1">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              Added
            </span>
          )}
        </div>
        {meta && <p className="text-xs text-gray-500 mt-1 ml-[92px]">{meta}</p>}
      </div>

      {expanded && (
        <div className="px-3 pb-3 border-t border-gray-100 pt-2 text-sm">
          {result.fit_reason && (
            <div className="mb-2">
              <p className="text-xs font-medium text-gray-500 mb-0.5">Why it's a fit</p>
              <p className="text-xs text-gray-700">{result.fit_reason}</p>
            </div>
          )}

          {result.description && (
            <div className="mb-2">
              <p className="text-xs font-medium text-gray-500 mb-0.5">Description</p>
              <p className="text-xs text-gray-600 line-clamp-3">{result.description}</p>
            </div>
          )}

          {result.requirements && (
            <div className="mb-2">
              <p className="text-xs font-medium text-gray-500 mb-0.5">Requirements</p>
              <ul className="text-xs text-gray-600 list-disc list-inside">
                {result.requirements.split("\n").filter(Boolean).slice(0, 5).map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex gap-2 mt-3">
            {result.url && (
              <a
                href={result.url}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="text-xs px-3 py-1.5 rounded border border-gray-300 text-gray-700 hover:bg-gray-50 transition-colors"
              >
                View Posting
              </a>
            )}
            {!result.added_to_tracker && (
              <button
                onClick={handleAdd}
                disabled={adding}
                className="text-xs px-3 py-1.5 rounded bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 transition-colors flex items-center gap-1.5"
              >
                {adding && (
                  <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                )}
                {addButtonLabel}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function SearchResultsPanel({
  isOpen,
  results,
  onClose,
  onAddToTracker,
  isSearching,
}) {
  if (!isOpen) return null;

  const sortedResults = [...results].sort((a, b) => {
    if ((b.job_fit || 0) !== (a.job_fit || 0)) return (b.job_fit || 0) - (a.job_fit || 0);
    return new Date(a.created_at) - new Date(b.created_at);
  });

  return (
    <div className="flex flex-col h-full border-l border-gray-200 bg-gray-50">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-gray-200 bg-white">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <h3 className="text-sm font-semibold text-gray-900">
            Jobs Found
            {results.length > 0 && (
              <span className="ml-1.5 text-xs font-normal text-gray-500">
                ({results.length})
              </span>
            )}
          </h3>
        </div>
        <button
          onClick={onClose}
          className="p-1 text-gray-400 hover:text-gray-600 rounded"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Results list */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
        {isSearching && results.length === 0 && (
          <div className="flex flex-col items-center justify-center py-8 text-gray-400">
            <svg className="w-8 h-8 animate-spin mb-2" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <p className="text-sm">Searching for jobs...</p>
          </div>
        )}

        {!isSearching && results.length === 0 && (
          <div className="flex flex-col items-center justify-center py-8 text-gray-400">
            <p className="text-sm">No results yet</p>
          </div>
        )}

        {sortedResults.map((result) => (
          <ResultCard
            key={result.id}
            result={result}
            onAddToTracker={onAddToTracker}
          />
        ))}

        {isSearching && results.length > 0 && (
          <div className="flex items-center justify-center py-3 text-gray-400">
            <svg className="w-4 h-4 animate-spin mr-2" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <p className="text-xs">Finding more jobs...</p>
          </div>
        )}
      </div>
    </div>
  );
}
