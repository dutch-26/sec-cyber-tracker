import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow fs reads from data/ directory one level up (for Vercel builds)
  serverExternalPackages: [],
  output: "standalone",
};

export default nextConfig;
