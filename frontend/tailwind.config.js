/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // OKLCH-unified blue ramp (hue locked at 255°, uniform ΔL)
        primary: {
          50:  '#ecf6ff', // oklch(97.0% 0.020 255)
          100: '#d7eaff', // oklch(93.0% 0.040 255)
          200: '#aed4ff', // oklch(86.0% 0.080 255)
          300: '#79b7ff', // oklch(77.0% 0.130 255)
          400: '#409aff', // oklch(68.5% 0.180 255)
          500: '#0078f8', // oklch(59.0% 0.215 255)
          600: '#005ddf', // oklch(51.0% 0.220 255)
          700: '#0047b6', // oklch(43.0% 0.195 255)
          800: '#00348a', // oklch(35.0% 0.160 255) — nav bg, 11.30:1 on white AAA
          900: '#002360', // oklch(27.5% 0.120 255)
        },
      },
    },
  },
  plugins: [],
}
