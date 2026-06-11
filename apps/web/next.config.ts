import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",               // 정적 SPA 빌드 → out/ (Firebase Hosting 용)
  images: { unoptimized: true },  // next/image 안 쓰지만 export 호환 위해 미리
};

export default nextConfig;
