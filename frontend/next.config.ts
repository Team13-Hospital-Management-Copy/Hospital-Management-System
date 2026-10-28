import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output: the Docker image only needs the files this produces, not the full
  // node_modules tree - see frontend/Dockerfile.
  output: "standalone",
};

export default nextConfig;
