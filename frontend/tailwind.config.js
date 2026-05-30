/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // 프리미엄 다크 모드에 어울리는 HSL 커스텀 테마 색상 정의
        brand: {
          dark: '#0f172a',
          card: '#1e293b',
          border: '#334155',
          accent: '#6366f1',
          highlight: '#818cf8',
        }
      }
    },
  },
  plugins: [],
}
