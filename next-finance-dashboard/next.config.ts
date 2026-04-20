import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Don't 308-redirect trailing slashes before the /fastapi/* rewrite fires.
  // Otherwise /fastapi/api/stats/ → 308 → /fastapi/api/stats → FastAPI 404
  // because FastAPI routes are canonicalized with a trailing slash.
  skipTrailingSlashRedirect: true,
  async rewrites() {
    return [
      {
        source: "/fastapi/:path*",
        destination: "http://localhost:8000/:path*",
      },
    ];
  },
};

export default nextConfig;
