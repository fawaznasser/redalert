import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        sand: "#efe6d4",
        ink: "#172026",
        ember: "#c9572b",
        steel: "#35586d",
        olive: "#64764a",
        cloud: "#f6f3ed",
      },
      boxShadow: {
        panel: "0 24px 50px rgba(23, 32, 38, 0.16)",
      },
    },
  },
  plugins: [],
};

export default config;
