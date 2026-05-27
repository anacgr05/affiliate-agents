import { NextRequest, NextResponse } from "next/server";
import { request as httpRequest, IncomingMessage } from "node:http";
import { Readable } from "node:stream";

// Set NEXT_PUBLIC_API_URL on Vercel, for example:
// https://your-backend.onrender.com
const API_BASE = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const parsedApiBase = new URL(API_BASE);

// For localhost: node:http with agent:false avoids ECONNRESET caused by uvicorn
// closing idle connections that the Node.js undici pool tries to reuse.
// For remote hosts: fetch supports HTTPS and has no pool issues.
const IS_LOCAL =
  parsedApiBase.hostname === "localhost" || parsedApiBase.hostname === "127.0.0.1";

const BACKEND_HOST = parsedApiBase.hostname;
const BACKEND_PORT = parseInt(
  parsedApiBase.port || (parsedApiBase.protocol === "https:" ? "443" : "80"),
  10
);

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
    stream.on("data", (chunk: Buffer) => chunks.push(chunk));
    stream.on("end", () => resolve(Buffer.concat(chunks).toString("utf-8")));
    stream.on("error", reject);
  });
}

async function getRequestBody(req: NextRequest): Promise<string | null> {
  if (req.method === "GET" || req.method === "HEAD") {
    return null;
  }

  const text = await req.text();
  return text || null;
}

async function proxyLocal(req: NextRequest, backendPath: string): Promise<NextResponse> {
  const bodyText = await getRequestBody(req);

  let res: IncomingMessage;

  try {
    res = await makeRequest(
      req.method,
      backendPath,
      bodyText,
      req.headers.get("Content-Type")
    );
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error(`[proxy-local] ${req.method} ${backendPath} → ${message}`);

    return NextResponse.json(
      { error: "Erro ao conectar no backend local", detail: message },
      { status: 502 }
    );
  }

  const contentType = (res.headers["content-type"] as string) ?? "application/json";

  if (contentType.includes("text/event-stream")) {
    const webStream = Readable.toWeb(res) as ReadableStream;

    return new NextResponse(webStream, {
      status: res.statusCode ?? 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        Connection: "keep-alive",
      },
    });
  }

  const body = await readBody(res);

  return new NextResponse(body, {
    status: res.statusCode ?? 200,
    headers: {
      "Content-Type": contentType,
    },
  });
}

async function proxyRemote(req: NextRequest, backendPath: string): Promise<NextResponse> {
  const bodyText = await getRequestBody(req);
  const contentType = req.headers.get("Content-Type");

  try {
    const res = await fetch(`${API_BASE}${backendPath}`, {
      method: req.method,
      headers: {
        ...(contentType ? { "Content-Type": contentType } : {}),
      },
      body: bodyText ?? undefined,
      cache: "no-store",
    });

    const responseContentType = res.headers.get("content-type") ?? "application/json";

    if (responseContentType.includes("text/event-stream")) {
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
      headers: {
        "Content-Type": responseContentType,
      },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error(`[proxy-remote] ${req.method} ${backendPath} → ${message}`);

    return NextResponse.json(
      { error: "Erro ao conectar no backend remoto", detail: message },
      { status: 502 }
    );
  }
}

async function proxy(req: NextRequest, path: string[]): Promise<NextResponse> {
  // IMPORTANTE:
  // Mantém a query string, por exemplo:
  // /api/agent/posts/stream?slug=meu-artigo
  // vira:
  // /agent/posts/stream?slug=meu-artigo
  const backendPath = `/agent/${path.join("/")}${req.nextUrl.search || ""}`;

  return IS_LOCAL ? proxyLocal(req, backendPath) : proxyRemote(req, backendPath);
}

export async function GET(
  req: NextRequest,
  context: { params: { path: string[] } | Promise<{ path: string[] }> }
) {
  const params = await Promise.resolve(context.params);
  return proxy(req, params.path);
}

export async function POST(
  req: NextRequest,
  context: { params: { path: string[] } | Promise<{ path: string[] }> }
) {
  const params = await Promise.resolve(context.params);
  return proxy(req, params.path);
}
