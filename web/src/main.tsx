import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { AccountProvider, ThemeProvider } from './account'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ThemeProvider>
        <AccountProvider>
          <App />
        </AccountProvider>
      </ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
