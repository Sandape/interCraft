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

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
