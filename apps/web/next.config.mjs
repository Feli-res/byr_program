const api = process.env.API_INTERNAL_URL || 'http://127.0.0.1:8080';
const config = {
  poweredByHeader: false,
  ...(process.env.DEPLOY_STANDALONE === 'true' ? {output: 'standalone'} : {}),
  async headers() { return [{source: '/:path*', headers: [{key:'X-Content-Type-Options',value:'nosniff'},{key:'Referrer-Policy',value:'strict-origin-when-cross-origin'}]}]; },
  // Allow a 10 MiB PDF plus multipart framing; the API enforces each purpose limit.
  experimental: {proxyClientMaxBodySize: 11 * 1024 * 1024},
  async rewrites() {
    if (process.env.DISABLE_DEV_PAGE === 'true') return [{source:'/dev-check',destination:'/not-found'}];
    return [
      {source: '/api/:path*', destination: `${api}/api/:path*`},
      {source: '/health/:path*', destination: `${api}/health/:path*`},
    ];
  },
};
export default config;
