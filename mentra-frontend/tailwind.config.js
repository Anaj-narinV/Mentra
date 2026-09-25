/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        bg: '#F3F5F0',
        surface: '#FFFFFF',
        ink: '#1F2A24',
        primary: { DEFAULT: '#2F4B3C', light: '#4F6F5B' },
        accent: '#B98B3E',
        line: '#DDD8CC',
        success: '#3F7A5C',
        warning: '#B9793E',
        danger: '#B23B3B',
        muted: '#8A8578',
      },
      fontFamily: {
        serif: ['"Fraunces"', 'ui-serif', 'Georgia', 'serif'],
        sans: ['"Public Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      maxWidth: {
        content: '760px',
      },
    },
  },
  plugins: [],
}
