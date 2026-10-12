import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "工业设备智能运维 Agent 平台",
    short_name: "工业运维 Agent",
    description: "企业级多模态工业设备智能诊断与知识治理平台",
    id: "/workspace",
    start_url: "/workspace",
    scope: "/",
    display: "standalone",
    background_color: "#f5f7fa",
    theme_color: "#0b5cad",
    lang: "zh-CN",
    orientation: "any",
    icons: [
      {
        src: "/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any",
      },
      {
        src: "/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "maskable",
      },
    ],
  };
}
