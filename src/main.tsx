import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'
import './modules/resume/styles/resume-classic-one-page.css'
import './modules/resume/styles/resume-compact-one-page.css'
import './modules/resume/styles/resume-modern-two-column.css'
import './modules/resume/styles/resume-editorial.css'
import './modules/resume/styles/resume-avatar.css'
import './modules/resume/styles/resume-block-flash.css'
import './modules/resume/styles/resume-muji-shell.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
// REQ-053 acceptance: surface boot errors so vite HMR shows them clearly
window.addEventListener('error', e => console.error('[BOOT ERROR]', e.message, e.filename + ':' + e.lineno, e.error?.stack?.substring(0, 500)))
window.addEventListener('unhandledrejection', e => console.error('[BOOT REJECTION]', String(e.reason)))
