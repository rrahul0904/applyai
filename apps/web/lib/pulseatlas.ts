const endpoint = process.env.NEXT_PUBLIC_PULSEATLAS_ENDPOINT;
const writeKey = process.env.NEXT_PUBLIC_PULSEATLAS_WRITE_KEY;

function storedId(storage: Storage, key: string, prefix: string) {
  let value = storage.getItem(key);
  if (!value) {
    value = `${prefix}_${crypto.randomUUID()}`;
    storage.setItem(key, value);
  }
  return value;
}

export async function trackPulseAtlasPage(path: string): Promise<boolean> {
  if (!endpoint || !writeKey) return false;
  const environment = process.env.NEXT_PUBLIC_PULSEATLAS_ENVIRONMENT === "preview" ? "preview" : process.env.NEXT_PUBLIC_PULSEATLAS_ENVIRONMENT === "development" ? "development" : "production";
  try {
    await fetch(endpoint, {
      method: "POST",
      headers: { "content-type": "application/json", "x-pulseatlas-write-key": writeKey },
      body: JSON.stringify({
        id: `evt_${crypto.randomUUID()}`,
        schemaVersion: 1,
        organizationId: "portfolio_primary",
        projectId: "proj_applyai",
        projectSlug: "applyai",
        environment,
        eventName: "page_view",
        eventCategory: "page",
        occurredAt: new Date().toISOString(),
        anonymousId: storedId(localStorage, "applyai_pa_aid", "anon"),
        sessionId: storedId(sessionStorage, "applyai_pa_sid", "session"),
        properties: { path: path.split("?")[0].split("#")[0] },
      }),
      keepalive: true,
    });
    return true;
  } catch {
    return false;
  }
}
