import { useEffect, useState } from "react";
import { fetchJobs, createJob, updateJob, deleteJob } from "../api";
import JobForm from "../components/JobForm";
import JobDetailPanel from "../components/JobDetailPanel";

const STATUS_COLORS = {
  saved: "bg-gray-100 text-gray-700",
  applied: "bg-blue-100 text-blue-700",
  interviewing: "bg-yellow-100 text-yellow-800",
  offer: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-700",
};

const STATUS_ORDER = { saved: 0, applied: 1, interviewing: 2, offer: 3, rejected: 4 };

const SORTABLE_COLUMNS = [
  { key: "company", label: "Company" },
  { key: "title", label: "Title" },
  { key: "location", label: "Location" },
  { key: "salary_min", label: "Salary" },
  { key: "status", label: "Status" },
  { key: "job_fit", label: "Fit" },
  { key: "tags", label: "Tags" },
  { key: "created_at", label: "Added" },
];

function compareJobs(a, b, column, direction) {
  let valA, valB;

  if (column === "status") {
    valA = STATUS_ORDER[a.status] ?? 99;
    valB = STATUS_ORDER[b.status] ?? 99;
  } else if (column === "salary_min") {
    valA = a.salary_min ?? (direction === "asc" ? Infinity : -Infinity);
    valB = b.salary_min ?? (direction === "asc" ? Infinity : -Infinity);
  } else if (column === "job_fit") {
    valA = a.job_fit ?? (direction === "asc" ? Infinity : -Infinity);
    valB = b.job_fit ?? (direction === "asc" ? Infinity : -Infinity);
  } else if (column === "created_at") {
    valA = new Date(a.created_at).getTime();
    valB = new Date(b.created_at).getTime();
  } else {
    valA = (a[column] ?? "").toString().toLowerCase();
    valB = (b[column] ?? "").toString().toLowerCase();
  }

  if (valA < valB) return direction === "asc" ? -1 : 1;
  if (valA > valB) return direction === "asc" ? 1 : -1;
  return 0;
}

export default function JobList({ refreshVersion }) {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingJob, setEditingJob] = useState(null);
  const [selectedJob, setSelectedJob] = useState(null);
  const [sortColumn, setSortColumn] = useState("created_at");
  const [sortDirection, setSortDirection] = useState("desc");

  useEffect(() => {
    loadJobs();
  }, [refreshVersion]);

  async function loadJobs() {
    try {
      const data = await fetchJobs();
      setJobs(data);
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(data) {
    await createJob(data);
    setShowForm(false);
    loadJobs();
  }

  async function handleUpdate(data) {
    await updateJob(editingJob.id, data);
    setEditingJob(null);
    loadJobs();
  }

  async function handleDelete(id) {
    if (!confirm("Delete this job application?")) return;
    await deleteJob(id);
    loadJobs();
  }

  function handleSort(column) {
    if (sortColumn === column) {
      setSortDirection((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortColumn(column);
      setSortDirection("asc");
    }
  }

  const sortedJobs = [...jobs].sort((a, b) => compareJobs(a, b, sortColumn, sortDirection));

  if (loading) {
    return <p className="text-gray-500 text-center py-12">Loading...</p>;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-gray-800">
          Applications ({jobs.length})
        </h2>
        {!showForm && !editingJob && (
          <button
            onClick={() => setShowForm(true)}
            className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 transition-colors"
          >
            + Add Job
          </button>
        )}
      </div>

      {showForm && (
        <div className="mb-6">
          <JobForm onSubmit={handleCreate} onCancel={() => setShowForm(false)} />
        </div>
      )}

      {editingJob && (
        <div className="mb-6">
          <JobForm
            initialData={editingJob}
            onSubmit={handleUpdate}
            onCancel={() => setEditingJob(null)}
          />
        </div>
      )}

      {jobs.length === 0 ? (
        <p className="text-gray-500 text-center py-12">
          No applications yet. Click "Add Job" to get started.
        </p>
      ) : (
        <div className="overflow-x-auto bg-white rounded-lg shadow">
          <table className="w-full text-left">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {SORTABLE_COLUMNS.map(({ key, label }) => (
                  <th
                    key={key}
                    onClick={() => handleSort(key)}
                    className="px-4 py-3 text-sm font-medium text-gray-600 cursor-pointer select-none hover:text-gray-900 transition-colors"
                  >
                    <span className="inline-flex items-center gap-1">
                      {label}
                      {sortColumn === key ? (
                        <span className="text-blue-600">{sortDirection === "asc" ? "▲" : "▼"}</span>
                      ) : (
                        <span className="text-gray-300">⇅</span>
                      )}
                    </span>
                  </th>
                ))}
                <th className="px-4 py-3 text-sm font-medium text-gray-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {sortedJobs.map((job) => (
                <tr
                  key={job.id}
                  onClick={() => setSelectedJob(job)}
                  className="hover:bg-gray-50 cursor-pointer"
                >
                  <td className="px-4 py-3 font-medium text-gray-900">
                    {job.url ? (
                      <a
                        href={job.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="text-blue-600 hover:underline"
                      >
                        {job.company}
                      </a>
                    ) : (
                      job.company
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-700">{job.title}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {job.location && <span>{job.location}</span>}
                    {job.remote_type && (
                      <span className="ml-1 text-xs text-gray-400">({job.remote_type})</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {job.salary_min || job.salary_max
                      ? `${job.salary_min ? `$${job.salary_min.toLocaleString()}` : "?"}–${job.salary_max ? `$${job.salary_max.toLocaleString()}` : "?"}`
                      : ""}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block px-2 py-1 text-xs font-medium rounded-full ${STATUS_COLORS[job.status] ?? ""}`}
                    >
                      {job.status.charAt(0).toUpperCase() + job.status.slice(1)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-amber-500 text-sm whitespace-nowrap">
                    {job.job_fit != null && (
                      <>{"★".repeat(job.job_fit)}{"☆".repeat(5 - job.job_fit)}</>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {job.tags && (
                      <div className="flex flex-wrap gap-1">
                        {job.tags.split(",").map((tag) => tag.trim()).filter(Boolean).map((tag) => (
                          <span key={tag} className="inline-block bg-gray-100 text-gray-600 text-xs px-2 py-0.5 rounded-full">
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {new Date(job.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedJob(null);
                          setEditingJob(job);
                        }}
                        className="text-sm text-blue-600 hover:underline"
                      >
                        Edit
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(job.id);
                        }}
                        className="text-sm text-red-600 hover:underline"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <JobDetailPanel
        job={selectedJob}
        isOpen={!!selectedJob}
        onClose={() => setSelectedJob(null)}
        onEdit={(job) => {
          setSelectedJob(null);
          setEditingJob(job);
        }}
      />
    </div>
  );
}
