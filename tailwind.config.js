/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'PingFang SC',
          'Hiragino Sans GB',
          'Microsoft YaHei',
          'sans-serif',
        ],
        mono: ['Menlo', 'Monaco', 'Consolas', 'monospace'],
      },
      colors: {
        // 语义化颜色令牌
        brand: {
          50: '#EFF6FF',
          100: '#DBEAFE',
          200: '#BFDBFE',
          300: '#93C5FD',
          400: '#60A5FA',
          500: '#3B82F6',
          600: '#2563EB',
          700: '#1D4ED8',
          900: '#0F172A',
        },
        surface: {
          DEFAULT: '#FFFFFF',
          subtle: '#F8FAFC',
          muted: '#F1F5F9',
          border: '#E2E8F0',
        },
        ink: {
          primary: '#0F172A',
          secondary: '#334155',
          tertiary: '#64748B',
          muted: '#94A3B8',
        },
        // 深色模式
        'dark-surface': {
          DEFAULT: '#0B1220',
          subtle: '#0F172A',
          muted: '#1E293B',
          border: '#1E293B',
        },
        'dark-ink': {
          primary: '#F1F5F9',
          secondary: '#CBD5E1',
          tertiary: '#94A3B8',
          muted: '#64748B',
        },
      },
      fontSize: {
        '2xs': ['11px', { lineHeight: '1.4' }],
        xs: ['12px', { lineHeight: '1.5' }],
        sm: ['13px', { lineHeight: '1.5' }],
        base: ['14px', { lineHeight: '1.6' }],
        md: ['15px', { lineHeight: '1.6' }],
        lg: ['16px', { lineHeight: '1.6' }],
        xl: ['18px', { lineHeight: '1.5' }],
        '2xl': ['20px', { lineHeight: '1.4' }],
        '3xl': ['24px', { lineHeight: '1.3' }],
        '4xl': ['30px', { lineHeight: '1.25' }],
      },
      boxShadow: {
        'notion-sm': '0 1px 2px 0 rgba(15, 23, 42, 0.04)',
        notion: '0 1px 3px 0 rgba(15, 23, 42, 0.06), 0 1px 2px -1px rgba(15, 23, 42, 0.04)',
        'notion-md': '0 4px 12px -2px rgba(15, 23, 42, 0.08), 0 2px 4px -2px rgba(15, 23, 42, 0.04)',
        'notion-lg': '0 12px 24px -4px rgba(15, 23, 42, 0.10), 0 4px 8px -2px rgba(15, 23, 42, 0.04)',
        focus: '0 0 0 3px rgba(59, 130, 246, 0.18)',
      },
      borderRadius: {
        DEFAULT: '4px',
        md: '6px',
        lg: '8px',
        xl: '12px',
      },
      transitionDuration: {
        DEFAULT: '200ms',
      },
      transitionTimingFunction: {
        DEFAULT: 'cubic-bezier(0.4, 0, 0.2, 1)',
      },
      keyframes: {
        'fade-in': {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-in-right': {
          '0%': { opacity: '0', transform: 'translateX(8px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        'pulse-soft': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.6' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      animation: {
        'fade-in': 'fade-in 200ms cubic-bezier(0.4, 0, 0.2, 1)',
        'slide-in-right': 'slide-in-right 200ms cubic-bezier(0.4, 0, 0.2, 1)',
        'pulse-soft': 'pulse-soft 2s ease-in-out infinite',
        shimmer: 'shimmer 1.5s linear infinite',
      },
    },
  },
  plugins: [],
}
