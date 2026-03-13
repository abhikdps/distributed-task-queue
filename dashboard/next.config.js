/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      { source: '/api/stats', destination: 'http://localhost:8080/api/stats' },
      { source: '/api/tasks', destination: 'http://localhost:8080/api/tasks' },
      { source: '/api/submit', destination: 'http://localhost:8080/api/submit' },
    ];
  },
};

module.exports = nextConfig;
