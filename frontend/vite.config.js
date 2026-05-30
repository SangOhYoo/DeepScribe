import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1', // 명시적으로 IPv4 루프백 바인딩 강제
    port: 3000, // 프론트엔드 개발 서버 포트 설정
    proxy: {
      // /api 경로의 요청을 FastAPI 서버(8002포트)로 프록시 처리합니다.
      '/api': {
        target: 'http://127.0.0.1:8002',
        changeOrigin: true,
        secure: false,
      },
      // 망가 원본 이미지를 받아오기 위한 미디어 서빙 프록시 설정
      '/media': {
        target: 'http://127.0.0.1:8002',
        changeOrigin: true,
        secure: false,
      }
    }
  }
})
