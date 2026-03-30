const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  (window.location.hostname === "localhost" ||
  window.location.hostname === "127.0.0.1"
    ? "http://localhost:8000"
    : "/api");
const TOKEN_STORAGE_KEY = "rvidia_access_token";

function clampScore(value) {
  if (value < 0) return 0;
  if (value > 100) return 100;
  return Math.round(value * 100) / 100;
}

function getWebGLRenderer() {
  try {
    const canvas = document.createElement("canvas");
    const gl =
      canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
    if (!gl) return null;
    const ext = gl.getExtension("WEBGL_debug_renderer_info");
    if (!ext) return null;
    return gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) || null;
  } catch {
    return null;
  }
}

function keywordScore(name, tiers) {
  if (!name) return 0;
  const lowered = String(name).toLowerCase();
  for (const [keyword, score] of tiers) {
    if (lowered.includes(keyword)) return score;
  }
  return 0;
}

function buildBrowserMachineProfile() {
  const logicalCores =
    typeof navigator !== "undefined" && navigator.hardwareConcurrency
      ? Number(navigator.hardwareConcurrency)
      : null;
  const physicalCores =
    logicalCores && logicalCores > 1
      ? Math.max(1, Math.floor(logicalCores / 2))
      : logicalCores;
  const deviceMemoryGb =
    typeof navigator !== "undefined" && navigator.deviceMemory
      ? Number(navigator.deviceMemory)
      : null;
  const memoryMb = deviceMemoryGb ? Math.round(deviceMemoryGb * 1024) : null;

  const platform = navigator?.platform || "Unknown";
  const userAgent = navigator?.userAgent || "";
  let osLabel = platform;
  const ua = userAgent.toLowerCase();
  if (ua.includes("windows")) osLabel = "Windows";
  else if (ua.includes("mac")) osLabel = "macOS";
  else if (ua.includes("linux")) osLabel = "Linux";

  const gpuModel = getWebGLRenderer();
  const cpuModel = logicalCores
    ? `${osLabel} (${logicalCores} threads)`
    : osLabel || userAgent || null;

  const cpuTier = [
    ["apple", 26],
    ["intel", 20],
    ["amd", 22],
  ];
  const gpuTier = [
    ["nvidia", 50],
    ["rtx", 58],
    ["radeon", 42],
    ["apple", 36],
    ["intel", 20],
  ];

  const cpuScore = clampScore(
    (physicalCores || 0) * 3.0 +
      (logicalCores || 0) * 1.0 +
      keywordScore(cpuModel, cpuTier),
  );
  const gpuScore = clampScore(keywordScore(gpuModel, gpuTier) || 10);
  const memoryScore = clampScore(memoryMb ? Math.min(100, (memoryMb / 1024) * 3.0) : 0);
  const machineScore = clampScore(
    0.35 * cpuScore + 0.55 * gpuScore + 0.1 * memoryScore,
  );

  return {
    os: osLabel,
    cpu_model: cpuModel,
    cpu_physical_cores: physicalCores || null,
    cpu_logical_cores: logicalCores || null,
    cpu_max_clock_mhz: null,
    gpu_model: gpuModel,
    gpu_vram: null,
    gpu_driver: null,
    gpu_vram_mb: null,
    ram_mb: memoryMb,
    ram_source: memoryMb ? "browser_estimate" : "unknown",
    cpu_score: cpuScore,
    gpu_score: gpuScore,
    ram_score: memoryScore,
    total_score: machineScore,
    scoring_version: "web-v1",
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
    if (response.status === 401) {
      try {
        localStorage.removeItem(TOKEN_STORAGE_KEY);
      } catch {
        // Ignore storage errors and continue throwing auth error.
      }
      throw new Error(body.detail || "Session expired. Please login again.");
    }
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

export async function listJobAccessRequests(token, jobId) {
  return request(`/p2p/jobs/${jobId}/requests`, {
    method: "GET",
    headers: buildHeaders(token),
  });
}

export async function listAcceptedHosts(token, jobId) {
  return request(`/p2p/jobs/${jobId}/accepted-hosts`, {
    method: "GET",
    headers: buildHeaders(token),
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
