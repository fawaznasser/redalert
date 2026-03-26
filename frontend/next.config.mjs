const rawBasePath = (process.env.NEXT_PUBLIC_SITE_BASE_PATH ?? "").trim();
const normalizedBasePath = rawBasePath
  ? rawBasePath === "/"
    ? ""
    : rawBasePath.startsWith("/")
      ? rawBasePath.replace(/\/+$/, "")
      : `/${rawBasePath.replace(/\/+$/, "")}`
  : "";

/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    typedRoutes: false
  },
  ...(normalizedBasePath ? { basePath: normalizedBasePath } : {})
};

export default nextConfig;
