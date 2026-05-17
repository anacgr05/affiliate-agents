import { NextRequest, NextResponse } from "next/server";
import { request as httpRequest, IncomingMessage } from "node:http";
import { Readable } from "node:stream";

// Set NEXT_PUBLIC_API_URL on Vercel (e.g. https://your-api.railway.app).
// Falls back to http://localhost:8000 for local development.
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const _parsed = new URL(API_BASE);

// For localhost: node:http with agent:false avoids ECONNRESET caused by uvicorn
// closing idle connections that the Node.js undici pool tries to reuse.
// For remote hosts: fetch supports HTTPS and has no pool issues.
const IS_LOCAL = _parsed.hostname === "localhost" || _parsed.hostname === "127.0.0.1";
const BACKEND_HOST = _parsed.hostname;
const BACKEND_PORT = parseInt(_parsed.port || (_parsed.protocol === "https:" ? "443" : "80"), 10);

function makeRequest(
  method: string,
  path: string,
  body: string | null,
  contentType: string | null
): Promise<IncomingMessage> {
  return new Promise((resolve, reject) => {
    const req = httpRequest(
      {
        hostname: BACKEND_HOST,
        port: BACKEND_PORT,
        path,
        method,
        agent: false,
        headers: {
          ...(contentType ? { "Content-Type": contentType } : {}),
          ...(body != null ? { "Content-Length": String(Buffer.byteLength(body)) } : {}),
        },
      },
      resolve
    );

    req.on("error", reject);
    req.setTimeout(45_000, () => req.destroy(new Error("backend timeout")));

    if (body) req.write(body);
    req.end();
  });
}

async function readBody(stream: IncomingMessage): Promise<string> {
  const chunks: Buffer[] = [];
  return new Promise((resolve, reject) => {
    stream.on("data", (c: Buffer) => chunks.push(c));
    stream.on("end", () => resolve(Buffer.concat(chunks).toString("utf-8")));
    stream.on("error", reject);
  });
}

async function proxyLocal(req: NextRequest, backendPath: string): Promise<NextResponse> {
  let bodyText: string | null = null;
  if (req.method !== "GET" && req.method !== "HEAD") {
    const t = await req.text();
    if (t) bodyText = t;
  }

  let res: IncomingMessage;
  try {
    res = await makeRequest(req.method, backendPath, bodyText, req.headers.get("Content-Type"));
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error(`[proxy] ${req.method} ${backendPath} → ${msg}`);
    return NextResponse.json({ error: msg }, { status: 502 });
  }

  const contentType = (res.headers["content-type"] as string) ?? "";

  if (contentType.includes("text/event-stream")) {
    const webStream = Readable.toWeb(res) as ReadableStream;
    return new NextResponse(webStream, {
      status: res.statusCode ?? 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
      },
    });
  }

  const body = await readBody(res);
  return new NextResponse(body, {
    status: res.statusCode ?? 200,
    headers: { "Content-Type": contentType || "application/json" },
  });
}

async function proxyRemote(req: NextRequest, backendPath: string): Promise<NextResponse> {
  let bodyText: string | null = null;
  if (req.method !== "GET" && req.method !== "HEAD") {
    const t = await req.text();
    if (t) bodyText = t;
  }

  try {
    const res = await fetch(`${API_BASE}${backendPath}`, {
      method: req.method,
      headers: { "Content-Type": "application/json" },
      body: bodyText ?? undefined,
    });

    const contentType = res.headers.get("content-type") ?? "application/json";

    if (contentType.includes("text/event-stream")) {
      return new NextResponse(res.body, {
        status: res.status,
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
          "X-Accel-Buffering": "no",
        },
      });
    }

    const data = await res.text();
    return new NextResponse(data, {
      status: res.status,
      headers: { "Content-Type": contentType },
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error(`[proxy] ${req.method} ${backendPath} → ${msg}`);
    return NextResponse.json({ error: msg }, { status: 502 });
  }
}

async function proxy(req: NextRequest, path: string[]): Promise<NextResponse> {
  const backendPath = `/agent/${path.join("/")}`;
  return IS_LOCAL ? proxyLocal(req, backendPath) : proxyRemote(req, backendPath);
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxy(req, (await params).path);
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxy(req, (await params).path);
}
