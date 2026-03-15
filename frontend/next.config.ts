import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["192.168.1.11", "192.168.3.72"],
  // /api/agent/* is handled by app/api/agent/[...path]/route.ts (keepalive: false)
  // No rewrites needed — the route handler proxies directly to localhost:8000
};

export default nextConfig;
