function JobDetailPanel({ job, isOpen, onClose, onEdit }) {
  if (!isOpen || !job) return null;

  const statusColors = {
    saved: "bg-gray-100 text-gray-800",
    applied: "bg-blue-100 text-blue-800",
    interviewing: "bg-yellow-100 text-yellow-800",
    offer: "bg-green-100 text-green-800",
    rejected: "bg-red-100 text-red-800",
  };

  const remoteTypeLabels = {
    onsite: "On-site",
    hybrid: "Hybrid",
    remote: "Remote",
  };

  function formatSalary(min, max) {
    if (!min && !max) return null;
    if (min && max) return `$${min.toLocaleString()} - $${max.toLocaleString()}`;
    if (min) return `$${min.toLocaleString()}+`;
    if (max) return `Up to $${max.toLocaleString()}`;
  }

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/30 z-40" onClick={onClose} />

      {/* Panel */}
      <div className="fixed right-0 top-0 h-full w-full max-w-2xl bg-white shadow-xl z-50 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b bg-gray-50">
          <div className="min-w-0 flex-1">
            <h2 className="font-semibold text-xl text-gray-900">{job.title}</h2>
            <p className="text-gray-600">{job.company}</p>
          </div>
          <div className="flex gap-2 ml-4">
            <button
              onClick={() => onEdit(job)}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              Edit
            </button>
            <button
              onClick={onClose}
              className="p-2 text-gray-500 hover:text-gray-700"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Status Badge */}
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

          {/* Job Fit */}
          {job.job_fit != null && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-1">Job Fit</h3>
              <span className="text-amber-500 text-lg">
                {"★".repeat(job.job_fit)}{"☆".repeat(5 - job.job_fit)}
              </span>
              <span className="ml-2 text-sm text-gray-500">{job.job_fit}/5</span>
            </div>
          )}

          {/* Basic Info */}
          {job.location && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-1">Location</h3>
              <p className="text-gray-900">{job.location}</p>
            </div>
          )}

          {formatSalary(job.salary_min, job.salary_max) && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-1">Salary</h3>
              <p className="text-gray-900">{formatSalary(job.salary_min, job.salary_max)}</p>
            </div>
          )}

          {/* URL */}
          {job.url && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-1">Job Posting</h3>
              <a
                href={job.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline break-words"
              >
                {job.url}
              </a>
            </div>
          )}

          {/* Requirements */}
          {job.requirements && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-2">Requirements</h3>
              <div className="bg-gray-50 rounded-lg p-4">
                <p className="text-gray-900 whitespace-pre-wrap">{job.requirements}</p>
              </div>
            </div>
          )}

          {/* Nice to Haves */}
          {job.nice_to_haves && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-2">Nice to Haves</h3>
              <div className="bg-gray-50 rounded-lg p-4">
                <p className="text-gray-900 whitespace-pre-wrap">{job.nice_to_haves}</p>
              </div>
            </div>
          )}

          {/* Notes */}
          {job.notes && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-2">Notes</h3>
              <div className="bg-gray-50 rounded-lg p-4">
                <p className="text-gray-900 whitespace-pre-wrap">{job.notes}</p>
              </div>
            </div>
          )}

          {/* Tags */}
          {job.tags && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-2">Tags</h3>
              <div className="flex flex-wrap gap-2">
                {job.tags.split(",").map((tag, i) => (
                  <span
                    key={i}
                    className="px-2 py-1 bg-gray-100 text-gray-700 rounded text-sm"
                  >
                    {tag.trim()}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Contact Info */}
          {(job.contact_name || job.contact_email) && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-2">Contact</h3>
              <div className="space-y-1">
                {job.contact_name && (
                  <p className="text-gray-900">{job.contact_name}</p>
                )}
                {job.contact_email && (
                  <a
                    href={`mailto:${job.contact_email}`}
                    className="text-blue-600 hover:underline block"
                  >
                    {job.contact_email}
                  </a>
                )}
              </div>
            </div>
          )}

          {/* Application Date */}
          {job.applied_date && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-1">Applied Date</h3>
              <p className="text-gray-900">
                {new Date(job.applied_date).toLocaleDateString()}
              </p>
            </div>
          )}

          {/* Source */}
          {job.source && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-1">Source</h3>
              <p className="text-gray-900">{job.source}</p>
            </div>
          )}

          {/* Timestamps */}
          <div className="pt-4 border-t text-xs text-gray-500">
            <p>Created: {new Date(job.created_at).toLocaleString()}</p>
            <p>Updated: {new Date(job.updated_at).toLocaleString()}</p>
          </div>
        </div>
      </div>
    </>
  );
}

export default JobDetailPanel;
