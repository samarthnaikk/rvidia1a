const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  (window.location.hostname === "localhost" ||
  window.location.hostname === "127.0.0.1"
    ? "http://localhost:8000"
    : "/api");

function clampScore(value) {
  if (!Number.isFinite(value)) return 0;
  if (value < 0) return 0;
  if (value > 100) return 100;
  return Math.round(value * 100) / 100;
}

function getWebGLRenderer() {
  try {
    const canvas = document.createElement("canvas");
    const gl = canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
    if (!gl) return null;
    const ext = gl.getExtension("WEBGL_debug_renderer_info");
    if (!ext) return null;
    return gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) || null;
  } catch {
    return null;
  }
}

function buildBrowserMachineProfile() {
  const logicalCores = navigator?.hardwareConcurrency ? Number(navigator.hardwareConcurrency) : null;
  const physicalCores = logicalCores && logicalCores > 1 ? Math.max(1, Math.floor(logicalCores / 2)) : logicalCores;
  const memoryGb = navigator?.deviceMemory ? Number(navigator.deviceMemory) : null;
  const memoryMb = memoryGb ? Math.round(memoryGb * 1024) : null;
  const gpuModel = getWebGLRenderer();
  const cpuModel = navigator?.platform || navigator?.userAgent || "Unknown";

  const cpuScore = clampScore((physicalCores || 0) * 3 + (logicalCores || 0) * 1.5);
  const gpuScore = clampScore(gpuModel ? 25 : 5);
  const memoryScore = clampScore(memoryMb ? memoryMb / 512 : 0);
  const machineScore = clampScore(0.35 * cpuScore + 0.5 * gpuScore + 0.15 * memoryScore);

  return {
    cpu_model: cpuModel,
    cpu_physical_cores: physicalCores,
    cpu_logical_cores: logicalCores,
    cpu_max_clock_mhz: null,
    gpu_model: gpuModel,
    gpu_vram: null,
    gpu_driver: null,
    gpu_vram_mb: null,
    memory_total_mb: memoryMb,
    cpu_score: cpuScore,
    gpu_score: gpuScore,
    memory_score: memoryScore,
    machine_score: machineScore,
    ranking_version: "web-v1",
  };
}

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

export async function listMarketplaceJobs(token) {
  return request("/p2p/jobs", {
    method: "GET",
    headers: buildHeaders(token),
  });
}

export async function requestJobAccess(token, jobId) {
  const machineProfile = buildBrowserMachineProfile();
  return request(`/p2p/jobs/${jobId}/request-access`, {
    method: "POST",
    headers: buildHeaders(token),
    body: JSON.stringify({ hardware_metadata: machineProfile }),
  });
}

export async function acceptJobAccess(token, jobId, requesterUserId = null) {
  return request(`/p2p/jobs/${jobId}/accept-access`, {
    method: "POST",
    headers: buildHeaders(token),
    body: JSON.stringify({ requester_user_id: requesterUserId }),
  });
}

export async function getJobAccessState(token, jobId) {
  return request(`/p2p/jobs/${jobId}/access`, {
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

export async function getP2PTelemetry(token) {
  return request("/p2p/telemetry", {
    method: "GET",
    headers: buildHeaders(token),
  });
}

export async function getContributorSummaries(token) {
  return request("/p2p/contributors/summary", {
    method: "GET",
    headers: buildHeaders(token),
  });
}

export async function getContributorHistory(token, nodeId, limit = 20) {
  return request(`/p2p/contributors/${nodeId}/history?limit=${limit}`, {
    method: "GET",
    headers: buildHeaders(token),
  });
}

export async function getDailyAnalytics(token, days = 14) {
  return request(`/p2p/analytics/daily?days=${days}`, {
    method: "GET",
    headers: buildHeaders(token),
  });
}
