import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

/**
 * Vite 建置設定
 * 整合 React 框架支援與 Tailwind CSS 樣式處理
 * build output 目錄設定為 dist，供 S3 部署使用
 */
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  build: {
    outDir: 'dist',
  },
})
