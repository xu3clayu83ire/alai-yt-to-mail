/**
 * 應用程式入口點
 * 掛載 React 應用至 DOM，設定 StrictMode 協助開發期間偵測潛在問題
 */

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('找不到 root 元素，請確認 index.html 包含 <div id="root"></div>');
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
