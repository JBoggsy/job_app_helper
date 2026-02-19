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
  if (!res.ok) throw new Error(data.error || "Connection test failed");
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
