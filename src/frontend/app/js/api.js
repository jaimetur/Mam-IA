// Calls to the server's API. Writes carry the app's header (the server refuses writes without it: CSRF).

export class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

export async function api(path, { method = "GET", body, raw = false } = {}) {
  const opts = { method, credentials: "same-origin", headers: {} };
  if (method !== "GET") opts.headers["x-mamia"] = "1";
  if (body !== undefined) {
    opts.headers["content-type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(path, opts);
  } catch (e) {
    throw new ApiError(0, "Sin conexión. Lo guardo y lo envío al volver la red.");
  }
  if (res.status === 401) {
    location.href = "/entrar?next=" + encodeURIComponent(location.pathname + location.search + location.hash);
    throw new ApiError(401, "Inicia sesión.");
  }
  if (raw) return res;
  let data = null;
  try { data = await res.json(); } catch (e) { /* empty body */ }
  if (!res.ok) {
    const d = data && data.detail;
    throw new ApiError(res.status, typeof d === "string" ? d : res.status === 422 ? "Revisa los datos." : `Error ${res.status}`);
  }
  return data;
}
