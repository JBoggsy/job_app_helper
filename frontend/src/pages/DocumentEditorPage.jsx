import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { fetchJobs, fetchJobDocument, fetchDocumentHistory, saveJobDocument } from "../api";
import DocumentEditor from "../components/DocumentEditor";
import { useAppContext } from "../contexts/AppContext";

const DOC_TYPE_LABELS = {
  cover_letter: "Cover Letter",
  resume: "Resume",
};

export default function DocumentEditorPage() {
  const { id, type } = useParams();
  const navigate = useNavigate();
  const { setChatOpen, onDocumentSaved } = useAppContext();

  const [job, setJob] = useState(null);
  const [document, setDocument] = useState(null);
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [showVersions, setShowVersions] = useState(false);
  const [copied, setCopied] = useState(false);

  const currentContentRef = useRef("");
  const docType = type || "cover_letter";
  const docLabel = DOC_TYPE_LABELS[docType] || docType;

  useEffect(() => {
    loadData();
  }, [id, type]);

  // Subscribe to agent document saves — reload when the agent saves a new
  // version of the document we're currently editing.
  useEffect(() => {
    return onDocumentSaved((data) => {
      if (data.job_id === Number(id) && data.doc_type === docType) {
        // Agent saved a new version — reload document + history
        fetchJobDocument(Number(id), docType)
          .then((doc) => {
            setDocument(doc);
            currentContentRef.current = doc.content || "";
            setHasChanges(false);
          })
          .catch(() => {});
        fetchDocumentHistory(Number(id), docType)
          .then((history) => setVersions(history))
          .catch(() => {});
      }
    });
  }, [id, docType, onDocumentSaved]);

  async function loadData() {
    setLoading(true);
    try {
      // Load job info
      const jobs = await fetchJobs();
      const found = jobs.find((j) => j.id === Number(id));
      if (!found) {
        navigate("/jobs", { replace: true });
        return;
      }
      setJob(found);

      // Load document
      try {
        const doc = await fetchJobDocument(Number(id), docType);
        setDocument(doc);
        currentContentRef.current = doc.content || "";
      } catch {
        // No document exists yet — start fresh
        setDocument(null);
        currentContentRef.current = "";
      }

      // Load version history
      try {
        const history = await fetchDocumentHistory(Number(id), docType);
        setVersions(history);
      } catch {
        setVersions([]);
      }
    } finally {
      setLoading(false);
    }
  }

  const handleEditorUpdate = useCallback((html) => {
    currentContentRef.current = html;
    setHasChanges(true);
  }, []);

  async function handleSave() {
    if (!currentContentRef.current.trim()) return;
    setSaving(true);
    try {
      const saved = await saveJobDocument(Number(id), docType, currentContentRef.current, "Manual edit");
      setDocument(saved);
      setHasChanges(false);
      // Refresh version history
      try {
        const history = await fetchDocumentHistory(Number(id), docType);
        setVersions(history);
      } catch {}
    } finally {
      setSaving(false);
    }
  }

  async function handleViewVersion(version) {
    setDocument(version);
    currentContentRef.current = version.content || "";
    setHasChanges(false);
    setShowVersions(false);
  }

  async function handleRestoreVersion(version) {
    setSaving(true);
    try {
      const saved = await saveJobDocument(Number(id), docType, version.content, `Restored from v${version.version}`);
      setDocument(saved);
      currentContentRef.current = saved.content || "";
      setHasChanges(false);
      const history = await fetchDocumentHistory(Number(id), docType);
      setVersions(history);
      setShowVersions(false);
    } finally {
      setSaving(false);
    }
  }

  function handleCopyToClipboard() {
    // Convert HTML to plain text
    const tmp = window.document.createElement("div");
    tmp.innerHTML = currentContentRef.current;
    const text = tmp.textContent || tmp.innerText || "";
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  function handleKeyDown(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === "s") {
      e.preventDefault();
      if (hasChanges) handleSave();
    }
  }

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [hasChanges]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <span className="inline-block w-6 h-6 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      {/* Top Bar */}
      <div className="flex items-center justify-between bg-white border-b px-4 py-2 rounded-t-lg shadow-sm">
        <div className="flex items-center gap-3">
          <Link to={`/jobs/${id}`} className="text-sm text-gray-500 hover:text-gray-700 inline-flex items-center gap-1">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back
          </Link>
          <div className="h-4 w-px bg-gray-300" />
          <div>
            <span className="text-sm font-medium text-gray-900">{docLabel}</span>
            {job && <span className="text-sm text-gray-500 ml-2">for {job.company} &mdash; {job.title}</span>}
          </div>
          {document && (
            <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded">v{document.version}</span>
          )}
          {hasChanges && (
            <span className="text-xs text-amber-600 bg-amber-50 px-2 py-0.5 rounded">Unsaved changes</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleCopyToClipboard}
            className="px-3 py-1.5 text-xs text-gray-600 border border-gray-300 rounded hover:bg-gray-50"
          >
            {copied ? "Copied!" : "Copy Text"}
          </button>
          {versions.length > 0 && (
            <button
              onClick={() => setShowVersions(!showVersions)}
              className="px-3 py-1.5 text-xs text-gray-600 border border-gray-300 rounded hover:bg-gray-50"
            >
              History ({versions.length})
            </button>
          )}
          <button
            onClick={() => setChatOpen(true)}
            className="px-3 py-1.5 text-xs bg-blue-50 text-blue-700 border border-blue-200 rounded hover:bg-blue-100"
          >
            AI Assistant
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !hasChanges}
            className="px-4 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>

      {/* Main content area */}
      <div className="flex flex-1 min-h-0">
        {/* Editor */}
        <div className="flex-1 flex flex-col bg-white rounded-b-lg shadow-sm overflow-hidden">
          <DocumentEditor
            content={document?.content || ""}
            onUpdate={handleEditorUpdate}
            placeholder={`Start writing your ${docLabel.toLowerCase()}...`}
          />
        </div>

        {/* Version History Sidebar */}
        {showVersions && (
          <div className="w-72 border-l bg-gray-50 flex flex-col overflow-hidden">
            <div className="px-4 py-3 border-b bg-white flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-900">Version History</h3>
              <button onClick={() => setShowVersions(false)} className="p-1 text-gray-400 hover:text-gray-600">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-2 space-y-1">
              {versions.map((v) => (
                <div
                  key={v.id}
                  className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                    document?.id === v.id
                      ? "border-blue-300 bg-blue-50"
                      : "border-gray-200 bg-white hover:border-gray-300"
                  }`}
                  onClick={() => handleViewVersion(v)}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-900">v{v.version}</span>
                    <span className="text-xs text-gray-400">
                      {new Date(v.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  {v.edit_summary && (
                    <p className="text-xs text-gray-500 mt-1 truncate">{v.edit_summary}</p>
                  )}
                  {document?.id !== v.id && document?.version !== v.version && (
                    <button
                      onClick={(e) => { e.stopPropagation(); handleRestoreVersion(v); }}
                      className="text-xs text-blue-600 hover:text-blue-800 mt-1"
                    >
                      Restore
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
