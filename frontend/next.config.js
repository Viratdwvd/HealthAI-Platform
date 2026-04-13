/** @type {import('next').NextConfig} */
const nextConfig = {
  // Remove standalone - causes issues without lockfile
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_BASE_URL || "http://api-gateway:8000"}/api/:path*`,
      },
      {
        source: "/auth/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_BASE_URL || "http://api-gateway:8000"}/auth/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
