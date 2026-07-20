// Thin fetch wrapper for the FastAPI backend. The backend already returns
// SPEC.md section 11 copy verbatim in `detail` for the documented failure
// cases (wrong file type, extraction timeout) — this module surfaces that
// message as-is rather than re-deriving it client-side.

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(status, detail) {
    const message = typeof detail === "string" ? detail : detail?.message;
    super(message || "Something went wrong. Please try again.");
    this.status = status;
    this.detail = detail;
  }
}

async function parseJsonSafely(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

async function request(path, options) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, options);
  } catch {
    throw new ApiError(0, "Could not reach the server. Check your connection and try again.");
  }

  const body = await parseJsonSafely(response);
  if (!response.ok) {
    throw new ApiError(response.status, body?.detail);
  }
  return body;
}

export function verifyLabel(imageFile, application) {
  const formData = new FormData();
  formData.append("image", imageFile);
  formData.append("brand_name", application.brandName);
  formData.append("class_type", application.classType);
  formData.append("alcohol_content", application.alcoholContent);
  formData.append("net_contents", application.netContents);
  formData.append("beverage_type", application.beverageType);

  return request("/api/verify", { method: "POST", body: formData });
}

export function submitBatch(csvFile, imageFiles) {
  const formData = new FormData();
  formData.append("csv", csvFile);
  for (const file of imageFiles) {
    formData.append("images", file);
  }
  return request("/api/verify-batch", { method: "POST", body: formData });
}

export function getBatchStatus(batchId) {
  return request(`/api/batch/${batchId}`, { method: "GET" });
}
