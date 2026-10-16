/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Static export: FastAPI serves ./out from the same origin (one Render service, no CORS).
  output: "export",
  trailingSlash: true,
};

export default nextConfig;
