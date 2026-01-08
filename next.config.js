/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Plotly.js requires some webpack configuration
  webpack: (config) => {
    config.resolve.alias = {
      ...config.resolve.alias,
      'plotly.js': 'plotly.js/dist/plotly',
    };
    return config;
  },
}

module.exports = nextConfig

