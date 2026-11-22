import sample from "./fixtures/normal.json";

export const PREVIEW_SITE = "test-fixture";

export function needsSignIn(search, hash) {
  const params = new URLSearchParams(search);
  const page = hash.replace(/^#\/?/, "");
  return params.has("id") || params.has("analysis")
    || ["login", "register", "forgot"].includes(page) || page.startsWith("reset/");
}

export async function fetchPreview(path, options = {}) {
  if (path.startsWith("/workbench/") && ["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname)) {
    try {
      const response = await globalThis.fetch(path, options);
      return response.status === 401 ? Response.json({}, { status: 404 }) : response;
    } catch {
      return Response.json({}, { status: 404 });
    }
  }
  const { method } = options;
  const response = method === "GET" ? sample.responses[path] : undefined;
  return Response.json(response?.body ?? {}, { status: response?.status ?? 404 });
}
