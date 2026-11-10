// D41: the local workbench's client. The dashboard has two clients and they never mix:
//   api.js        GET only, the server's read-only endpoints. Everywhere.
//   workbench.js  this file. Only when the page is served by the local workbench
//                 (scripts/demo_launcher.py on 127.0.0.1), which says so at
//                 /workbench/capabilities; the server has no /workbench route.
// Its POSTs start or stop an analysis or a replay, find a file, open a folder window
// on this computer, or save a provisional camera. None of them reaches a signal, and
// no body can carry anything but short text, numbers and lane positions: never a
// picture or a file's bytes (NFR-13). The video stays in the browser.

export const READS = [
  /^\/workbench\/capabilities$/,
  /^\/workbench\/cameras$/,
  /^\/workbench\/jobs\/current$/,
  /^\/workbench\/replay\/clips$/,
  /^\/workbench\/replay\/state$/,
];
export const ACTIONS = ["/workbench/locate", "/workbench/folder", "/workbench/cameras", "/workbench/jobs",
  "/workbench/jobs/stop", "/workbench/replay/start", "/workbench/replay/stop", "/workbench/camera/start"];

// A body is plain data: short strings, finite numbers, booleans, and arrays or
// objects of those, a few levels deep. Anything else is refused before sending.
export function plainBody(value, depth = 0) {
  if (depth > 4) return false;
  if (value === null || typeof value === "boolean") return true;
  if (typeof value === "number") return Number.isFinite(value);
  if (typeof value === "string") return value.length <= 300;
  if (Array.isArray(value)) return value.length <= 8 && value.every((v) => plainBody(v, depth + 1));
  if (Object.getPrototypeOf(value) === Object.prototype) {
    const entries = Object.entries(value);
    return entries.length <= 8 && entries.every(([, v]) => plainBody(v, depth + 1));
  }
  return false;
}

async function reply(response) {
  let data = null;
  try { data = await response.json(); } catch { /* no JSON body */ }
  if (!response.ok) return { status: "error", code: response.status, reason: data?.error || data?.detail || `refused (${response.status})` };
  return { status: "ok", data };
}

export async function wbGet(path, fetcher = globalThis.fetch) {
  if (!READS.some((pattern) => pattern.test(path))) throw new Error(`workbench: ${path} is not a workbench read`);
  try {
    return await reply(await fetcher(path, { method: "GET", headers: { accept: "application/json" } }));
  } catch (error) {
    return { status: "error", reason: `the workbench is not answering (${error.message})` };
  }
}

export async function wbPost(path, body = {}, fetcher = globalThis.fetch) {
  if (!ACTIONS.includes(path)) throw new Error(`workbench: ${path} is not a workbench action`);
  if (!plainBody(body)) throw new Error("workbench: a body carries plain data only");
  try {
    return await reply(await fetcher(path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) }));
  } catch (error) {
    return { status: "error", reason: `the workbench is not answering (${error.message})` };
  }
}

// The same fingerprint as scripts/workbench.py: SHA-256 over "size:<n>" and the
// file's first, middle and last 1 MiB. Read here, in the browser; only the hex
// digest is sent, so the workbench can find this file on disk without the browser
// knowing its path or sending its bytes.
export const CHUNK = 1 << 20;
const readBytes = (blob) => (typeof blob.arrayBuffer === "function" ? blob.arrayBuffer() : new Promise((resolve, reject) => {
  const reader = new FileReader();
  reader.onload = () => resolve(reader.result);
  reader.onerror = () => reject(reader.error);
  reader.readAsArrayBuffer(blob);
}));
export async function fingerprint(file, subtle = globalThis.crypto?.subtle, chunk = CHUNK) {
  if (!subtle) throw new Error("this browser cannot fingerprint a file here (no Web Crypto)");
  const size = file.size;
  const offsets = [...new Set([0, Math.max(0, Math.floor(size / 2) - Math.floor(chunk / 2)), Math.max(0, size - chunk)])].sort((a, b) => a - b);
  const parts = [new TextEncoder().encode(`size:${size}`)];
  for (const offset of offsets) parts.push(new Uint8Array(await readBytes(file.slice(offset, offset + chunk))));
  const joined = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let at = 0;
  for (const part of parts) { joined.set(part, at); at += part.length; }
  const digest = new Uint8Array(await subtle.digest("SHA-256", joined));
  return [...digest].map((b) => b.toString(16).padStart(2, "0")).join("");
}
