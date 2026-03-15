import { NextRequest, NextResponse } from "next/server";
import { request as httpRequest, IncomingMessage } from "node:http";
import { Readable } from "node:stream";

const BACKEND_HOST = "localhost";
const BACKEND_PORT = 8000;

/**
 * Proxy using node:http with agent:false — a fresh TCP connection per request.
 *
 * Root cause of ECONNRESET: Node.js undici (used by global fetch) pools
 * connections. Uvicorn with --timeout-keep-alive 0 closes idle connections
 * on the server side; undici doesn't notice until it tries to reuse the
 * dead socket → ECONNRESET on every other request.
 *
 * agent:false bypasses the pool entirely and always opens a new socket.
 * headersTimeout:10_000 makes stale connections fail in <10s instead of 60s.
 */
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
        agent: false, // no connection pooling — fresh socket every time
        headers: {
          ...(contentType ? { "Content-Type": contentType } : {}),
          ...(body != null ? { "Content-Length": String(Buffer.byteLength(body)) } : {}),
        },
      },
      resolve
    );

    req.on("error", reject);

    // Fail fast on dead connections (ECONNRESET fires instantly with agent:false).
    // 45s covers the slowest legitimate operation (Writer LLM ~38s, ChromaDB
    // model loading ~30s). For truly down backends ECONNREFUSED fires in <1s.
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

async function proxy(req: NextRequest, path: string[]): Promise<NextResponse> {
  const backendPath = `/agent/${path.join("/")}`;

  let bodyText: string | null = null;
  if (req.method !== "GET" && req.method !== "HEAD") {
    const t = await req.text();
    if (t) bodyText = t;
  }

  let res: IncomingMessage;
  try {
    res = await makeRequest(
      req.method,
      backendPath,
      bodyText,
      req.headers.get("Content-Type")
    );
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error(`[proxy] ${req.method} ${backendPath} → ${msg}`);
    return NextResponse.json({ error: msg }, { status: 502 });
  }

  const contentType = (res.headers["content-type"] as string) ?? "";

  // SSE: stream the node Readable → Web ReadableStream without buffering
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

  // Regular response
  const body = await readBody(res);
  return new NextResponse(body, {
    status: res.statusCode ?? 200,
    headers: { "Content-Type": contentType || "application/json" },
  });
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
