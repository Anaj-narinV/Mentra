import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import { AuthProvider } from './state/AuthContext.jsx'
import { MentraDataProvider } from './state/MentraDataContext.jsx'
import { ChatProvider } from './state/ChatContext.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <MentraDataProvider>
          <ChatProvider>
            <App />
          </ChatProvider>
        </MentraDataProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
