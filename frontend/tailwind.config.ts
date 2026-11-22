import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        pitwall: {
          bg: '#0B0F17',          // Base Dark HUD canvas
          surface: '#121824',     // Panel / Card background
          surfaceHighlight: '#1A2234',
          border: '#1E293B',      // Subtle HUD divider
          accent: '#E10600',      // Formula 1 Red
          accentHover: '#B80500',
          textMuted: '#94A3B8',   // WCAG AA compliant on #0B0F17 (contrast > 5.5:1)
          textNormal: '#E2E8F0',  // High contrast body text
          textBright: '#FFFFFF',  // Headings & highlights
          success: '#10B981',
          warning: '#F59E0B',
          danger: '#EF4444',
          telemetryDeltaFast: '#10B981', // Driver 1 faster (green)
          telemetryDeltaSlow: '#EF4444', // Driver 1 slower (red)
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
} satisfies Config;
