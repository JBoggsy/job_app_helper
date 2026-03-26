function getApiBase() {
  if (window.__TAURI_INTERNALS__) {
    return `http://localhost:${window.__FLASK_PORT__ || 5000}`;
  }
  return "";
}

const API_BASE = getApiBase();
const BASE = `${API_BASE}/api/jobs`;
const CHAT_BASE = `${API_BASE}/api/chat`;
const PROFILE_BASE = `${API_BASE}/api/profile`;
const CONFIG_BASE = `${API_BASE}/api/config`;
const RESUME_BASE = `${API_BASE}/api/resume`;

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

// Application Todos API

export async function fetchJobTodos(jobId) {
  const res = await fetch(`${BASE}/${jobId}/todos`);
  if (!res.ok) throw new Error("Failed to fetch todos");
  return res.json();
}

export async function createJobTodo(jobId, data) {
  const res = await fetch(`${BASE}/${jobId}/todos`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to create todo");
  return res.json();
}

export async function updateJobTodo(jobId, todoId, data) {
  const res = await fetch(`${BASE}/${jobId}/todos/${todoId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to update todo");
  return res.json();
}

export async function deleteJobTodo(jobId, todoId) {
  const res = await fetch(`${BASE}/${jobId}/todos/${todoId}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete todo");
}

// Chat API

export async function fetchConversations() {
  const res = await fetch(`${CHAT_BASE}/conversations`);
  if (!res.ok) throw new Error("Failed to fetch conversations");
  return res.json();
}

export async function createConversation(title) {
  const res = await fetch(`${CHAT_BASE}/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error("Failed to create conversation");
  return res.json();
}

export async function fetchConversation(id) {
  const res = await fetch(`${CHAT_BASE}/conversations/${id}`);
  if (!res.ok) throw new Error("Failed to fetch conversation");
  return res.json();
}

export async function deleteConversation(id) {
  const res = await fetch(`${CHAT_BASE}/conversations/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to delete conversation");
}

export async function streamMessage(conversationId, content, onEvent, { signal } = {}) {
  const res = await fetch(
    `${CHAT_BASE}/conversations/${conversationId}/messages`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
      signal,
    }
  );

  if (!res.ok) throw new Error("Failed to send message");
  return _readSSE(res, onEvent, signal);
}

async function _readSSE(res, onEvent, signal) {
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  // If aborted, cancel the reader
  if (signal) {
    signal.addEventListener("abort", () => reader.cancel(), { once: true });
  }

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      let currentEvent = null;
      for (const line of lines) {
        if (line.startsWith("event: ")) {
          currentEvent = line.slice(7).trim();
        } else if (line.startsWith("data: ") && currentEvent) {
          try {
            const data = JSON.parse(line.slice(6));
            onEvent({ event: currentEvent, data });
          } catch (e) {
            console.error("Failed to parse SSE data:", e);
          }
          currentEvent = null;
        }
      }
    }
  } catch (e) {
    if (e.name === "AbortError") return;
    throw e;
  }
}

// Message Feedback API

export async function sendMessageFeedback(conversationId, messageId, signal, comment = "") {
  const res = await fetch(
    `${CHAT_BASE}/conversations/${conversationId}/messages/${messageId}/feedback`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ signal, comment }),
    }
  );
  if (!res.ok) throw new Error("Failed to send feedback");
}

// Search Results API

export async function fetchSearchResults(conversationId) {
  const res = await fetch(`${CHAT_BASE}/conversations/${conversationId}/search-results`);
  if (!res.ok) throw new Error("Failed to fetch search results");
  return res.json();
}

export async function addSearchResultToTracker(conversationId, resultId) {
  const res = await fetch(
    `${CHAT_BASE}/conversations/${conversationId}/search-results/${resultId}/add-to-tracker`,
    { method: "POST" }
  );
  const data = await res.json();
  if (!res.ok && res.status !== 409) throw new Error(data.error || "Failed to add to tracker");
  return data;
}

// Profile API

export async function fetchProfile() {
  const res = await fetch(PROFILE_BASE);
  if (!res.ok) throw new Error("Failed to fetch profile");
  return res.json();
}

export async function updateProfile(content) {
  const res = await fetch(PROFILE_BASE, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!res.ok) throw new Error("Failed to update profile");
  return res.json();
}

// Onboarding API

export async function fetchOnboardingStatus() {
  const res = await fetch(`${PROFILE_BASE}/onboarding-status`);
  if (!res.ok) throw new Error("Failed to fetch onboarding status");
  return res.json();
}

export async function createOnboardingConversation() {
  const res = await fetch(`${CHAT_BASE}/onboarding/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) throw new Error("Failed to create onboarding conversation");
  return res.json();
}

export async function kickOnboarding(conversationId, onEvent, { signal } = {}) {
  const res = await fetch(`${CHAT_BASE}/onboarding/kick`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ conversation_id: conversationId }),
    signal,
  });
  if (!res.ok) throw new Error("Failed to kick onboarding");
  return _readSSE(res, onEvent, signal);
}

export async function streamOnboardingMessage(conversationId, content, onEvent, { signal } = {}) {
  const res = await fetch(
    `${CHAT_BASE}/onboarding/conversations/${conversationId}/messages`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
      signal,
    }
  );
  if (!res.ok) throw new Error("Failed to send onboarding message");
  return _readSSE(res, onEvent, signal);
}

// Config API

export async function fetchConfig() {
  const res = await fetch(CONFIG_BASE);
  if (!res.ok) throw new Error("Failed to fetch config");
  return res.json();
}

export async function updateConfig(config) {
  const res = await fetch(CONFIG_BASE, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!res.ok) throw new Error("Failed to update config");
  return res.json();
}

export async function testConnection(provider, apiKey, model) {
  const res = await fetch(`${CONFIG_BASE}/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider, api_key: apiKey, model }),
  });
  const data = await res.json();
  if (!res.ok) {
    const err = new Error(data.error || "Connection test failed");
    err.errorType = data.error_type || "unknown";
    throw err;
  }
  return data;
}

export async function fetchModels(provider, apiKey) {
  const res = await fetch(`${CONFIG_BASE}/models`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider, api_key: apiKey }),
  });
  const data = await res.json();
  return data;
}

export async function fetchProviders() {
  const res = await fetch(`${CONFIG_BASE}/providers`);
  if (!res.ok) throw new Error("Failed to fetch providers");
  return res.json();
}

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/api/health`);
  // Note: health endpoint returns 503 if not configured, but we still want the data
  const data = await res.json();
  return data;
}

// Resume API

export async function uploadResume(file) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(RESUME_BASE, {
    method: "POST",
    body: formData,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Failed to upload resume");
  return data;
}

export async function fetchResume() {
  const res = await fetch(RESUME_BASE);
  if (!res.ok) throw new Error("Failed to fetch resume");
  return res.json();
}

export async function deleteResume() {
  const res = await fetch(RESUME_BASE, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete resume");
  return res.json();
}

export async function parseResumeWithLLM() {
  const res = await fetch(`${RESUME_BASE}/parse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Failed to parse resume");
  return data;
}

// Job Documents API

export async function fetchJobDocument(jobId, docType) {
  const res = await fetch(`${BASE}/${jobId}/documents?type=${encodeURIComponent(docType)}`);
  if (res.status === 204) return null;
  if (!res.ok) throw new Error("Failed to fetch document");
  return res.json();
}

export async function fetchDocumentHistory(jobId, docType) {
  const res = await fetch(`${BASE}/${jobId}/documents/history?type=${encodeURIComponent(docType)}`);
  if (!res.ok) throw new Error("Failed to fetch document history");
  return res.json();
}

export async function saveJobDocument(jobId, docType, content, editSummary) {
  const res = await fetch(`${BASE}/${jobId}/documents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ doc_type: docType, content, edit_summary: editSummary }),
  });
  if (!res.ok) throw new Error("Failed to save document");
  return res.json();
}

export async function deleteJobDocument(jobId, docId) {
  const res = await fetch(`${BASE}/${jobId}/documents/${docId}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete document");
}
