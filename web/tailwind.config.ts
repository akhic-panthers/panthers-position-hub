import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Panthers brand
        panthers: {
          blue: "#0085CA",
          bright: "#1CA3E0",
          black: "#101820",
          silver: "#BFC0BF",
        },
        // dark surfaces (NextGen / trade-tool aesthetic)
        ink: {
          950: "#0A0C0E",
          900: "#0F1318",
          850: "#15191E",
          800: "#1B2026",
          700: "#262C33",
          600: "#3A434B",
        },
        // portability / impact tiers
        tier: {
          high: "#10B981",
          mixed: "#F59E0B",
          low: "#EF4444",
        },
        // section accents
        defense: "#DC2626",
        offense: "#0085CA",
        matchup: "#7C3AED",
        // semantic
        border: "#262C33",
        background: "#0A0C0E",
        foreground: "#E6EAED",
        muted: "#8A949C",
        card: "#15191E",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      maxWidth: {
        content: "1720px",
      },
      borderRadius: {
        xl: "0.875rem",
      },
      keyframes: {
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        shimmer: { "100%": { transform: "translateX(100%)" } },
      },
      animation: {
        "fade-in": "fade-in 0.25s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
