/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        pitch: {
          deep: "var(--pitch-deep)",
          mid: "var(--pitch-mid)",
        },
        night: "var(--night-sky)",
        floodlight: "var(--floodlight)",
        trophy: "var(--trophy-gold)",
        kit: {
          home: "var(--kit-home)",
          away: "var(--kit-away)",
        },
        whistle: "var(--whistle-red)",
        turf: "var(--turf-line)",
      },
      fontFamily: {
        display: ["var(--font-display)", "Impact", "sans-serif"],
        body: ["var(--font-body)", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};