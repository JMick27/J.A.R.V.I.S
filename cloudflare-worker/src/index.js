const JSON_HEADERS = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store",
  "x-content-type-options": "nosniff",
};

const requestBuckets = new Map();

function json(data, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: JSON_HEADERS });
}

function rateLimited(request) {
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  const install = (request.headers.get("X-JARVIS-Install") || "unknown").slice(0, 80);
  const key = `${ip}:${install}`;
  const now = Date.now();
  const bucket = requestBuckets.get(key) || [];
  const recent = bucket.filter((time) => now - time < 60_000);
  recent.push(now);
  requestBuckets.set(key, recent);
  return recent.length > 30;
}

function modelIsApproved(model) {
  return /^gemini-[0-9]+(?:\.[0-9]+)*-flash(?:-[a-z0-9.-]+)?$/i.test(model);
}

async function proxyGemini(path, init, env) {
  const upstream = await fetch(`https://generativelanguage.googleapis.com/v1beta/${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      "x-goog-api-key": env.GEMINI_API_KEY,
    },
  });
  return new Response(upstream.body, {
    status: upstream.status,
    headers: JSON_HEADERS,
  });
}

export default {
  async fetch(request, env) {
    if (!env.GEMINI_API_KEY) {
      return json({ error: "AI service secret is not configured" }, 503);
    }
    if (rateLimited(request)) {
      return json({ error: "Too many requests. Please wait a moment." }, 429);
    }

    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/health") {
      return json({ status: "online" });
    }
    if (request.method === "GET" && url.pathname === "/v1/models") {
      const upstream = await fetch("https://generativelanguage.googleapis.com/v1beta/models?pageSize=100", {
        headers: { "x-goog-api-key": env.GEMINI_API_KEY },
      });
      if (!upstream.ok) {
        return new Response(upstream.body, { status: upstream.status, headers: JSON_HEADERS });
      }
      const data = await upstream.json();
      data.models = (data.models || []).filter((item) => {
        const name = String(item.name || "").replace(/^models\//, "");
        const methods = item.supportedGenerationMethods || [];
        return modelIsApproved(name) && methods.includes("generateContent");
      });
      return json(data);
    }
    if (request.method !== "POST" || url.pathname !== "/v1/generate") {
      return json({ error: "Not found" }, 404);
    }

    const length = Number(request.headers.get("content-length") || 0);
    const maxBytes = Number(env.MAX_REQUEST_BYTES || 12_582_912);
    if (length > maxBytes) {
      return json({ error: "Request is too large" }, 413);
    }

    let payload;
    try {
      const raw = await request.text();
      if (new TextEncoder().encode(raw).length > maxBytes) {
        return json({ error: "Request is too large" }, 413);
      }
      payload = JSON.parse(raw);
    } catch {
      return json({ error: "Invalid JSON" }, 400);
    }

    const model = String(payload.model || "").replace(/^models\//, "");
    if (!modelIsApproved(model)) {
      return json({ error: "Model is not approved" }, 400);
    }
    if (!Array.isArray(payload.contents) || payload.contents.length === 0) {
      return json({ error: "Contents are required" }, 400);
    }

    const body = {
      contents: payload.contents,
      ...(payload.systemInstruction ? { systemInstruction: payload.systemInstruction } : {}),
      ...(payload.generationConfig ? { generationConfig: payload.generationConfig } : {}),
    };
    return proxyGemini(`models/${encodeURIComponent(model)}:generateContent`, {
      method: "POST",
      body: JSON.stringify(body),
    }, env);
  },
};
