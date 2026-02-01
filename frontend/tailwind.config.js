/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      /* Align with website breakpoints for consistent mobile/desktop layout */
      screens: {
        xs: '400px',
        sm: '640px',
        md: '768px',
        lg: '1024px',
        xl: '1280px',
      },
      colors: {
        // Visible Manus 设计系统颜色
        background: '#09090b',
        surface: {
          DEFAULT: '#18181b',
          secondary: '#27272a',
        },
        // Alarm severity colors (保留原有)
        critical: '#EF4444',
        warning: '#F59E0B',
        info: '#3B82F6',
        // Risk level colors (保留原有)
        'risk-high': '#DC2626',
        'risk-medium': '#EA580C',
        'risk-low': '#16A34A',
        // Status colors (保留原有)
        active: '#10B981',
        inactive: '#6B7280',
        // Diagnostic agent colors
        diagnostic: {
          planner: '#f59e0b',    // amber-500
          collector: '#3b82f6',  // blue-500
          analyzer: '#8b5cf6',    // purple-500
          correlation: '#ec4899', // pink-500
          generator: '#10b981',   // green-500
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
    },
  },
  plugins: [],
}






