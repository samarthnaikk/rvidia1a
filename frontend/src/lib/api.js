const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  (window.location.hostname === "localhost" ||
  window.location.hostname === "127.0.0.1"
    ? "http://localhost:8000"
    : "/api");

function buildHeaders(token, extraHeaders = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...extraHeaders,
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (Array.isArray(body.detail)) {
      const details = body.detail
        .map((item) => `${item.loc?.join(".") || "request"}: ${item.msg}`)
        .join("; ");
      throw new Error(details || "Validation failed");
    }
    throw new Error(body.detail || "Request failed");
  }
  return body;
}

export async function signup(payload) {
  return request("/auth/signup", {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify(payload),
  });
}

export async function login(payload) {
  return request("/auth/login", {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify(payload),
  });
}

export async function getMe(token) {
  return request("/auth/me", {
    method: "GET",
    headers: buildHeaders(token),
  });
}

export async function createJob(token, payload) {
  return request("/jobs", {
    method: "POST",
    headers: buildHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function listJobs(token) {
  return request("/jobs", {
    method: "GET",
    headers: buildHeaders(token),
  });
}

export async function listOpenJobs(token) {
  return request("/jobs/open", {
    method: "GET",
    headers: buildHeaders(token),
  });
}

export async function getJob(token, jobId) {
  return request(`/jobs/${jobId}`, {
    method: "GET",
    headers: buildHeaders(token),
  });
}

export async function registerHost(token, jobId, nodeId) {
  return request(`/p2p/jobs/${jobId}/register-host`, {
    method: "POST",
    headers: buildHeaders(token),
    body: JSON.stringify({ node_id: nodeId }),
  });
}

export async function getPeers(token, jobId) {
  return request(`/p2p/jobs/${jobId}/peers`, {
    method: "GET",
    headers: buildHeaders(token),
  });
}
