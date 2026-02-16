const BASE = "/api/jobs";

export async function fetchJobs() {
  const res = await fetch(BASE);
  if (!res.ok) throw new Error("Failed to fetch jobs");
  return res.json();
}

export async function createJob(data) {
  const res = await fetch(BASE, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to create job");
  return res.json();
}

export async function updateJob(id, data) {
  const res = await fetch(`${BASE}/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to update job");
  return res.json();
}

export async function deleteJob(id) {
  const res = await fetch(`${BASE}/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete job");
}
