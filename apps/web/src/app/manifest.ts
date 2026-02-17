import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Green Permit Intake",
    short_name: "Permit Intake",
    description: "経営許可・運賃届出の入力とExcel生成",
    start_url: "/",
    display: "standalone",
    background_color: "#f1f5ef",
    theme_color: "#164033",
    icons: [
      {
        src: "/icon-192.png",
        sizes: "192x192",
        type: "image/png"
      },
      {
        src: "/icon-512.png",
        sizes: "512x512",
        type: "image/png"
      }
    ]
  };
}
