import { useState, useEffect, useRef } from 'react';
import { fetchModels } from '../api';

const cache = new Map();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

function getCached(key) {
  const entry = cache.get(key);
  if (entry && Date.now() - entry.ts < CACHE_TTL) return entry.models;
  cache.delete(key);
  return null;
}

function setCache(key, models) {
  cache.set(key, { models, ts: Date.now() });
}

export default function ModelCombobox({ provider, apiKey, value, onChange, placeholder, className }) {
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("");
  const wrapperRef = useRef(null);
  const inputRef = useRef(null);

  // Fetch models when provider/apiKey change
  useEffect(() => {
    if (!provider) {
      setModels([]);
      return;
    }
    if (provider !== "ollama" && !apiKey) {
      setModels([]);
      return;
    }

    const cacheKey = `${provider}:${apiKey || ""}`;
    const cached = getCached(cacheKey);
    if (cached) {
      setModels(cached);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchModels(provider, apiKey).then((data) => {
      if (cancelled) return;
      if (data.error) {
        setError(data.error);
        setModels([]);
      } else {
        setModels(data.models || []);
        setCache(cacheKey, data.models || []);
      }
    }).catch((err) => {
      if (cancelled) return;
      setError(err.message);
      setModels([]);
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });

    return () => { cancelled = true; };
  }, [provider, apiKey]);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClick(e) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const filtered = models.filter((m) => {
    const q = (filter || value || "").toLowerCase();
    if (!q) return true;
    return m.id.toLowerCase().includes(q) || (m.name && m.name.toLowerCase().includes(q));
  });

  function handleInputChange(e) {
    const val = e.target.value;
    setFilter(val);
    onChange(val);
    if (!open && models.length > 0) setOpen(true);
  }

  function handleSelect(modelId) {
    onChange(modelId);
    setFilter("");
    setOpen(false);
  }

  function handleInputFocus() {
    if (models.length > 0) setOpen(true);
  }

  function toggleDropdown() {
    if (models.length > 0) {
      setOpen(!open);
      if (!open) inputRef.current?.focus();
    }
  }

  const hasModels = models.length > 0;

  return (
    <div ref={wrapperRef} className="relative">
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={handleInputChange}
          onFocus={handleInputFocus}
          placeholder={placeholder}
          className={className || "w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"}
        />
        <button
          type="button"
          onClick={toggleDropdown}
          tabIndex={-1}
          className="absolute inset-y-0 right-0 flex items-center pr-2 text-gray-400 hover:text-gray-600"
        >
          {loading ? (
            <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
            </svg>
          ) : hasModels ? (
            <svg className={`w-4 h-4 transition-transform ${open ? "rotate-180" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          ) : null}
        </button>
      </div>

      {/* Dropdown */}
      {open && hasModels && (
        <ul className="absolute z-50 mt-1 w-full max-h-60 overflow-auto bg-white border border-gray-200 rounded-lg shadow-lg">
          {filtered.length === 0 ? (
            <li className="px-3 py-2 text-sm text-gray-400">No matching models</li>
          ) : (
            filtered.map((m) => (
              <li
                key={m.id}
                onClick={() => handleSelect(m.id)}
                className={`px-3 py-2 text-sm cursor-pointer hover:bg-blue-50 ${
                  m.id === value ? "bg-blue-50 font-medium" : ""
                }`}
              >
                <span className="text-gray-900">{m.id}</span>
                {m.name && m.name !== m.id && (
                  <span className="ml-2 text-gray-400 text-xs">{m.name}</span>
                )}
              </li>
            ))
          )}
        </ul>
      )}

      {/* Error warning */}
      {error && !loading && (
        <p className="mt-1 text-xs text-amber-600">
          Could not load models — you can still type a model name manually.
        </p>
      )}
    </div>
  );
}
