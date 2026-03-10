import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { fetchJobs, fetchHealth } from "../api";
import { useAppContext } from "../contexts/AppContext";

const STATUS_COLORS = {
  saved: "bg-gray-100 text-gray-700",
  applied: "bg-blue-100 text-blue-700",
  interviewing: "bg-yellow-100 text-yellow-800",
  offer: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-700",
};

export default function HomePage() {
  const { setChatOpen } = useAppContext();
  const [jobs, setJobs] = useState([]);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetchJobs().catch(() => []),
      fetchHealth().catch(() => null),
    ]).then(([jobsData, healthData]) => {
      setJobs(jobsData);
      setHealth(healthData);
      setLoading(false);
    });
  }, []);

  const recentJobs = [...jobs]
    .sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at))
    .slice(0, 5);

  const statusCounts = jobs.reduce((acc, j) => {
    acc[j.status] = (acc[j.status] || 0) + 1;
    return acc;
  }, {});

  const llmConfigured = health?.llm?.configured;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-32">
        <span className="inline-block w-6 h-6 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>

      {/* Quick Status Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow-sm p-4">
          <p className="text-sm text-gray-500">Total Jobs</p>
          <p className="text-2xl font-bold text-gray-900">{jobs.length}</p>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4">
          <p className="text-sm text-gray-500">Applied</p>
          <p className="text-2xl font-bold text-blue-700">{statusCounts.applied || 0}</p>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4">
          <p className="text-sm text-gray-500">Interviewing</p>
          <p className="text-2xl font-bold text-yellow-700">{statusCounts.interviewing || 0}</p>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4">
          <p className="text-sm text-gray-500">Offers</p>
          <p className="text-2xl font-bold text-green-700">{statusCounts.offer || 0}</p>
        </div>
      </div>

      {/* AI Status */}
      {!llmConfigured && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex items-center justify-between">
          <div>
            <p className="font-medium text-amber-800">AI Assistant not configured</p>
            <p className="text-sm text-amber-700">Set up your LLM provider to use the AI chat assistant.</p>
          </div>
          <Link to="/settings" className="px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 text-sm">
            Configure
          </Link>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Recent Jobs */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Recent Jobs</h2>
            <Link to="/jobs" className="text-sm text-blue-600 hover:text-blue-800">View all</Link>
          </div>
          {recentJobs.length === 0 ? (
            <p className="text-sm text-gray-500">No jobs yet. <Link to="/jobs" className="text-blue-600 hover:underline">Add your first job</Link> or <button onClick={() => setChatOpen(true)} className="text-blue-600 hover:underline">ask the AI assistant</button> to find some.</p>
          ) : (
            <div className="space-y-2">
              {recentJobs.map((job) => (
                <Link key={job.id} to={`/jobs/${job.id}`} className="flex items-center justify-between p-2 rounded hover:bg-gray-50 transition-colors">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-gray-900 text-sm truncate">{job.title}</p>
                    <p className="text-xs text-gray-500 truncate">{job.company}</p>
                  </div>
                  <span className={`ml-2 px-2 py-0.5 text-xs font-medium rounded-full ${STATUS_COLORS[job.status] ?? ""}`}>
                    {job.status}
                  </span>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Quick Actions */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h2>
          <div className="space-y-3">
            <Link to="/jobs" className="flex items-center gap-3 p-3 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors">
              <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              <div>
                <p className="font-medium text-gray-900 text-sm">Add a Job</p>
                <p className="text-xs text-gray-500">Manually track a new job application</p>
              </div>
            </Link>
            <button onClick={() => setChatOpen(true)} className="w-full flex items-center gap-3 p-3 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors text-left">
              <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
              </svg>
              <div>
                <p className="font-medium text-gray-900 text-sm">Open AI Assistant</p>
                <p className="text-xs text-gray-500">Search for jobs, get recommendations, write cover letters</p>
              </div>
            </button>
            <Link to="/profile" className="flex items-center gap-3 p-3 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors">
              <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
              <div>
                <p className="font-medium text-gray-900 text-sm">Edit Profile</p>
                <p className="text-xs text-gray-500">Update your job preferences and upload your resume</p>
              </div>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
