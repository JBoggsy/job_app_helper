import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { fetchJobs, updateJob, deleteJob, fetchJobTodos, createJobTodo, updateJobTodo, deleteJobTodo, fetchJobDocument } from "../api";
import JobForm from "../components/JobForm";

const CATEGORY_META = {
  document: { icon: "\uD83D\uDCC4", label: "Documents" },
  question: { icon: "\u2753", label: "Application Questions" },
  assessment: { icon: "\uD83D\uDCDD", label: "Assessments" },
  reference: { icon: "\uD83D\uDCCB", label: "References" },
  other: { icon: "\uD83D\uDCCC", label: "Other" },
};

const CATEGORY_ORDER = ["document", "question", "assessment", "reference", "other"];

const statusColors = {
  saved: "bg-gray-100 text-gray-800",
  applied: "bg-blue-100 text-blue-800",
  interviewing: "bg-yellow-100 text-yellow-800",
  offer: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-800",
};

const remoteTypeLabels = { onsite: "On-site", hybrid: "Hybrid", remote: "Remote" };

function formatSalary(min, max) {
  if (!min && !max) return null;
  if (min && max) return `$${min.toLocaleString()} - $${max.toLocaleString()}`;
  if (min) return `$${min.toLocaleString()}+`;
  if (max) return `Up to $${max.toLocaleString()}`;
}

export default function JobDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [todos, setTodos] = useState([]);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newTodoTitle, setNewTodoTitle] = useState("");
  const [newTodoCategory, setNewTodoCategory] = useState("other");
  const [newTodoDescription, setNewTodoDescription] = useState("");
  const [expandedTodos, setExpandedTodos] = useState(new Set());
  const [hasCoverLetter, setHasCoverLetter] = useState(false);
  const [hasResume, setHasResume] = useState(false);

  useEffect(() => {
    loadJob();
  }, [id]);

  async function loadJob() {
    setLoading(true);
    try {
      const jobs = await fetchJobs();
      const found = jobs.find((j) => j.id === Number(id));
      if (found) {
        setJob(found);
        loadTodos(found.id);
        // Check for documents
        fetchJobDocument(found.id, "cover_letter").then(() => setHasCoverLetter(true)).catch(() => setHasCoverLetter(false));
        fetchJobDocument(found.id, "resume").then(() => setHasResume(true)).catch(() => setHasResume(false));
      } else {
        navigate("/jobs", { replace: true });
      }
    } finally {
      setLoading(false);
    }
  }

  const loadTodos = useCallback(async (jobId) => {
    try {
      const data = await fetchJobTodos(jobId || job?.id);
      setTodos(data);
    } catch (err) {
      console.error("Failed to load todos:", err);
    }
  }, [job?.id]);

  async function handleUpdate(data) {
    await updateJob(job.id, data);
    setEditing(false);
    loadJob();
  }

  async function handleDelete() {
    if (!confirm("Delete this job application?")) return;
    await deleteJob(job.id);
    navigate("/jobs", { replace: true });
  }

  async function handleToggleTodo(todo) {
    try {
      const updated = await updateJobTodo(job.id, todo.id, { completed: !todo.completed });
      setTodos((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
    } catch (err) { console.error("Failed to toggle todo:", err); }
  }

  async function handleDeleteTodo(todoId) {
    try {
      await deleteJobTodo(job.id, todoId);
      setTodos((prev) => prev.filter((t) => t.id !== todoId));
    } catch (err) { console.error("Failed to delete todo:", err); }
  }

  async function handleAddTodo(e) {
    e.preventDefault();
    if (!newTodoTitle.trim()) return;
    try {
      const created = await createJobTodo(job.id, {
        title: newTodoTitle.trim(),
        category: newTodoCategory,
        description: newTodoDescription.trim(),
      });
      setTodos((prev) => [...prev, created]);
      setNewTodoTitle("");
      setNewTodoCategory("other");
      setNewTodoDescription("");
      setShowAddForm(false);
    } catch (err) { console.error("Failed to add todo:", err); }
  }

  function toggleExpanded(todoId) {
    setExpandedTodos((prev) => {
      const next = new Set(prev);
      if (next.has(todoId)) next.delete(todoId); else next.add(todoId);
      return next;
    });
  }

  if (loading) return <p className="text-gray-500 text-center py-12">Loading...</p>;
  if (!job) return null;

  const grouped = {};
  for (const todo of todos) {
    const cat = todo.category || "other";
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(todo);
  }
  const completedCount = todos.filter((t) => t.completed).length;

  if (editing) {
    return (
      <div className="max-w-3xl mx-auto">
        <JobForm initialData={job} onSubmit={handleUpdate} onCancel={() => setEditing(false)} />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <button onClick={() => navigate("/jobs")} className="text-sm text-gray-500 hover:text-gray-700 mb-2 inline-flex items-center gap-1">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
            Back to Jobs
          </button>
          <h1 className="text-2xl font-bold text-gray-900">{job.title}</h1>
          <p className="text-lg text-gray-600">{job.company}</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setEditing(true)} className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">Edit</button>
          <button onClick={handleDelete} className="px-4 py-2 text-sm bg-red-50 text-red-700 rounded-lg hover:bg-red-100">Delete</button>
        </div>
      </div>

      {/* Status & Meta */}
      <div className="bg-white rounded-lg shadow-sm p-6 space-y-4">
        <div className="flex items-center gap-3">
          <span className={`px-3 py-1 rounded-full text-sm font-medium ${statusColors[job.status] || statusColors.saved}`}>
            {job.status || "saved"}
          </span>
          {job.remote_type && (
            <span className="px-3 py-1 rounded-full text-sm font-medium bg-purple-100 text-purple-800">
              {remoteTypeLabels[job.remote_type] || job.remote_type}
            </span>
          )}
        </div>

        {job.job_fit != null && (
          <div>
            <h3 className="text-sm font-semibold text-gray-700 mb-1">Job Fit</h3>
            <span className="text-amber-500 text-lg">{"\u2605".repeat(job.job_fit)}{"\u2606".repeat(5 - job.job_fit)}</span>
            <span className="ml-2 text-sm text-gray-500">{job.job_fit}/5</span>
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          {job.location && <div><h3 className="text-sm font-semibold text-gray-700 mb-1">Location</h3><p className="text-gray-900">{job.location}</p></div>}
          {formatSalary(job.salary_min, job.salary_max) && <div><h3 className="text-sm font-semibold text-gray-700 mb-1">Salary</h3><p className="text-gray-900">{formatSalary(job.salary_min, job.salary_max)}</p></div>}
          {job.source && <div><h3 className="text-sm font-semibold text-gray-700 mb-1">Source</h3><p className="text-gray-900">{job.source}</p></div>}
          {job.applied_date && <div><h3 className="text-sm font-semibold text-gray-700 mb-1">Applied Date</h3><p className="text-gray-900">{new Date(job.applied_date).toLocaleDateString()}</p></div>}
        </div>

        {job.url && (
          <div>
            <h3 className="text-sm font-semibold text-gray-700 mb-1">Job Posting</h3>
            <a href={job.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline break-words">{job.url}</a>
          </div>
        )}

        {(job.contact_name || job.contact_email) && (
          <div>
            <h3 className="text-sm font-semibold text-gray-700 mb-1">Contact</h3>
            {job.contact_name && <p className="text-gray-900">{job.contact_name}</p>}
            {job.contact_email && <a href={`mailto:${job.contact_email}`} className="text-blue-600 hover:underline block">{job.contact_email}</a>}
          </div>
        )}

        {job.tags && (
          <div>
            <h3 className="text-sm font-semibold text-gray-700 mb-2">Tags</h3>
            <div className="flex flex-wrap gap-2">
              {job.tags.split(",").map((tag, i) => (
                <span key={i} className="px-2 py-1 bg-gray-100 text-gray-700 rounded text-sm">{tag.trim()}</span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Documents */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Documents</h2>
        <div className="grid grid-cols-2 gap-3">
          <Link
            to={`/jobs/${job.id}/documents/cover_letter`}
            className="flex items-center gap-3 p-3 rounded-lg border border-gray-200 hover:border-blue-300 hover:bg-blue-50 transition-colors"
          >
            <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <div>
              <p className="text-sm font-medium text-gray-900">Cover Letter</p>
              <p className="text-xs text-gray-500">{hasCoverLetter ? "View & edit" : "Create new"}</p>
            </div>
            {hasCoverLetter && <span className="ml-auto text-xs text-green-600 bg-green-50 px-2 py-0.5 rounded">Exists</span>}
          </Link>
          <Link
            to={`/jobs/${job.id}/documents/resume`}
            className="flex items-center gap-3 p-3 rounded-lg border border-gray-200 hover:border-blue-300 hover:bg-blue-50 transition-colors"
          >
            <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            <div>
              <p className="text-sm font-medium text-gray-900">Tailored Resume</p>
              <p className="text-xs text-gray-500">{hasResume ? "View & edit" : "Create new"}</p>
            </div>
            {hasResume && <span className="ml-auto text-xs text-green-600 bg-green-50 px-2 py-0.5 rounded">Exists</span>}
          </Link>
        </div>
      </div>

      {/* Application Steps */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-gray-900">
            Application Steps
            {todos.length > 0 && <span className="ml-2 text-sm font-normal text-gray-500">{completedCount}/{todos.length} completed</span>}
          </h2>
          <button onClick={() => setShowAddForm(!showAddForm)} className="text-xs px-3 py-1.5 text-gray-600 hover:text-gray-800 border border-gray-300 rounded hover:bg-gray-50">
            + Add
          </button>
        </div>

        {todos.length > 0 && (
          <div className="w-full bg-gray-200 rounded-full h-1.5 mb-3">
            <div className="bg-green-500 h-1.5 rounded-full transition-all duration-300" style={{ width: `${(completedCount / todos.length) * 100}%` }} />
          </div>
        )}

        {showAddForm && (
          <form onSubmit={handleAddTodo} className="bg-gray-50 rounded-lg p-3 mb-3 space-y-2">
            <input type="text" value={newTodoTitle} onChange={(e) => setNewTodoTitle(e.target.value)}
              placeholder="Step title (e.g., Submit cover letter)" className="w-full px-3 py-1.5 text-sm border rounded focus:outline-none focus:ring-1 focus:ring-blue-400" autoFocus />
            <div className="flex gap-2">
              <select value={newTodoCategory} onChange={(e) => setNewTodoCategory(e.target.value)} className="px-2 py-1.5 text-sm border rounded focus:outline-none focus:ring-1 focus:ring-blue-400">
                {CATEGORY_ORDER.map((cat) => <option key={cat} value={cat}>{CATEGORY_META[cat].icon} {CATEGORY_META[cat].label}</option>)}
              </select>
              <input type="text" value={newTodoDescription} onChange={(e) => setNewTodoDescription(e.target.value)}
                placeholder="Description (optional)" className="flex-1 px-3 py-1.5 text-sm border rounded focus:outline-none focus:ring-1 focus:ring-blue-400" />
            </div>
            <div className="flex gap-2 justify-end">
              <button type="button" onClick={() => setShowAddForm(false)} className="text-xs px-3 py-1.5 text-gray-600 hover:text-gray-800">Cancel</button>
              <button type="submit" disabled={!newTodoTitle.trim()} className="text-xs px-3 py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50">Add Step</button>
            </div>
          </form>
        )}

        {todos.length > 0 ? (
          <div className="space-y-3">
            {CATEGORY_ORDER.filter((cat) => grouped[cat]?.length > 0).map((cat) => (
              <div key={cat}>
                <div className="flex items-center gap-1.5 mb-1.5">
                  <span className="text-sm">{CATEGORY_META[cat].icon}</span>
                  <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">{CATEGORY_META[cat].label}</span>
                </div>
                <div className="space-y-1">
                  {grouped[cat].map((todo) => (
                    <div key={todo.id} className={`group flex items-start gap-2 px-3 py-2 rounded-lg border ${todo.completed ? "bg-green-50 border-green-200" : "bg-white border-gray-200 hover:border-gray-300"}`}>
                      <input type="checkbox" checked={todo.completed} onChange={() => handleToggleTodo(todo)}
                        className="mt-0.5 h-4 w-4 rounded border-gray-300 text-green-600 focus:ring-green-500 cursor-pointer" />
                      <div className="flex-1 min-w-0">
                        <button onClick={() => todo.description && toggleExpanded(todo.id)}
                          className={`text-sm text-left w-full ${todo.completed ? "line-through text-gray-400" : "text-gray-900"} ${todo.description ? "cursor-pointer hover:text-blue-600" : "cursor-default"}`}>
                          {todo.title}
                          {todo.description && <span className="ml-1 text-gray-400 text-xs">{expandedTodos.has(todo.id) ? "\u25BE" : "\u25B8"}</span>}
                        </button>
                        {todo.description && expandedTodos.has(todo.id) && (
                          <p className="text-xs text-gray-500 mt-1 whitespace-pre-wrap">{todo.description}</p>
                        )}
                      </div>
                      <button onClick={() => handleDeleteTodo(todo.id)}
                        className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 transition-opacity p-0.5" title="Remove step">
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-gray-400 italic">
            Add application steps manually to track your progress, or ask the AI assistant to extract them.
          </p>
        )}
      </div>

      {/* Requirements */}
      {job.requirements && (
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Requirements</h2>
          <p className="text-gray-900 whitespace-pre-wrap">{job.requirements}</p>
        </div>
      )}

      {/* Nice to Haves */}
      {job.nice_to_haves && (
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Nice to Haves</h2>
          <p className="text-gray-900 whitespace-pre-wrap">{job.nice_to_haves}</p>
        </div>
      )}

      {/* Notes */}
      {job.notes && (
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Notes</h2>
          <p className="text-gray-900 whitespace-pre-wrap">{job.notes}</p>
        </div>
      )}

      {/* Timestamps */}
      <div className="text-xs text-gray-500 pb-8">
        <p>Created: {new Date(job.created_at).toLocaleString()}</p>
        <p>Updated: {new Date(job.updated_at).toLocaleString()}</p>
      </div>
    </div>
  );
}
