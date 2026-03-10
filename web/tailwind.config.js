/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Ice Rink Blues (Primary)
        ice: {
          50: '#E6F4FB',
          100: '#CCE9F7',
          200: '#99D3EF',
          300: '#66BDE7',
          400: '#33A7DF',
          500: '#4A9FE8', // Main ice blue
          600: '#3B7FBA',
          700: '#2C5F8B',
          800: '#1D405D',
          900: '#0E202E',
        },
        // Team Reds (Accent)
        'team-red': {
          300: '#F4A5AA',
          500: '#E63946', // Main team red
          700: '#B82D37',
        },
        // Status Colors
        win: '#10B981',      // Green
        loss: '#EF4444',     // Red
        tie: '#F59E0B',      // Yellow/Amber
      },
      fontFamily: {
        sans: ['DM Sans', 'system-ui', 'sans-serif'],
        display: ['Barlow Condensed', 'system-ui', 'sans-serif'],
        mono: ['Roboto Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}
