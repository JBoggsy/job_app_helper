import { useState } from "react";

const STATUS_OPTIONS = ["saved", "applied", "interviewing", "offer", "rejected"];
const REMOTE_OPTIONS = ["", "onsite", "hybrid", "remote"];

export default function JobForm({ onSubmit, initialData, onCancel }) {
  const [form, setForm] = useState({
    company: initialData?.company ?? "",
    title: initialData?.title ?? "",
    url: initialData?.url ?? "",
    status: initialData?.status ?? "saved",
    salary_min: initialData?.salary_min ?? "",
    salary_max: initialData?.salary_max ?? "",
    location: initialData?.location ?? "",
    remote_type: initialData?.remote_type ?? "",
    source: initialData?.source ?? "",
    applied_date: initialData?.applied_date ?? "",
    contact_name: initialData?.contact_name ?? "",
    contact_email: initialData?.contact_email ?? "",
    tags: initialData?.tags ?? "",
    notes: initialData?.notes ?? "",
  });

  function handleChange(e) {
    const { name, value, type } = e.target;
    setForm({ ...form, [name]: type === "number" ? (value === "" ? "" : Number(value)) : value });
  }

  function handleSubmit(e) {
    e.preventDefault();
    const payload = { ...form };
    if (payload.salary_min === "") payload.salary_min = null;
    if (payload.salary_max === "") payload.salary_max = null;
    if (payload.applied_date === "") payload.applied_date = null;
    if (payload.remote_type === "") payload.remote_type = null;
    onSubmit(payload);
  }

  const inputCls = "w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500";

  return (
    <form onSubmit={handleSubmit} className="space-y-4 bg-white p-6 rounded-lg shadow">
      {/* Company & Title */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Company <span className="text-red-500">*</span>
          </label>
          <input name="company" value={form.company} onChange={handleChange} required className={inputCls} />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Title <span className="text-red-500">*</span>
          </label>
          <input name="title" value={form.title} onChange={handleChange} required className={inputCls} />
        </div>
      </div>

      {/* URL & Status */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">URL</label>
          <input name="url" value={form.url} onChange={handleChange} type="url" placeholder="https://..." className={inputCls} />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
          <select name="status" value={form.status} onChange={handleChange} className={inputCls}>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Salary & Location */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Salary Min</label>
          <input name="salary_min" value={form.salary_min} onChange={handleChange} type="number" min="0" placeholder="e.g. 80000" className={inputCls} />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Salary Max</label>
          <input name="salary_max" value={form.salary_max} onChange={handleChange} type="number" min="0" placeholder="e.g. 120000" className={inputCls} />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Location</label>
          <input name="location" value={form.location} onChange={handleChange} placeholder="e.g. New York, NY" className={inputCls} />
        </div>
      </div>

      {/* Remote Type, Source, Applied Date */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Remote Type</label>
          <select name="remote_type" value={form.remote_type} onChange={handleChange} className={inputCls}>
            {REMOTE_OPTIONS.map((r) => (
              <option key={r} value={r}>{r ? r.charAt(0).toUpperCase() + r.slice(1) : "— Select —"}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Source</label>
          <input name="source" value={form.source} onChange={handleChange} placeholder="e.g. LinkedIn, Referral" className={inputCls} />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Applied Date</label>
          <input name="applied_date" value={form.applied_date} onChange={handleChange} type="date" className={inputCls} />
        </div>
      </div>

      {/* Contact Info */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Contact Name</label>
          <input name="contact_name" value={form.contact_name} onChange={handleChange} placeholder="Recruiter / hiring manager" className={inputCls} />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Contact Email</label>
          <input name="contact_email" value={form.contact_email} onChange={handleChange} type="email" placeholder="recruiter@company.com" className={inputCls} />
        </div>
      </div>

      {/* Tags */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Tags</label>
        <input name="tags" value={form.tags} onChange={handleChange} placeholder="Comma-separated, e.g. python, startup, series-b" className={inputCls} />
      </div>

      {/* Notes */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
        <textarea name="notes" value={form.notes} onChange={handleChange} rows={3} className={inputCls} />
      </div>

      <div className="flex gap-3">
        <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 transition-colors">
          {initialData ? "Save Changes" : "Add Job"}
        </button>
        <button type="button" onClick={onCancel} className="border border-gray-300 px-4 py-2 rounded-md hover:bg-gray-50 transition-colors">
          Cancel
        </button>
      </div>
    </form>
  );
}
