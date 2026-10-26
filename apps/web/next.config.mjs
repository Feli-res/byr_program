const api = process.env.API_INTERNAL_URL || 'http://127.0.0.1:8080';
const config = {
  poweredByHeader: false,
  // Allow a 10 MiB PDF plus multipart framing; the API enforces each purpose limit.
  experimental: {proxyClientMaxBodySize: 11 * 1024 * 1024},
  async rewrites() {
    return [
      {source: '/api/:path*', destination: `${api}/api/:path*`},
      {source: '/health/:path*', destination: `${api}/health/:path*`},
    ];
  },
};
export default config;
