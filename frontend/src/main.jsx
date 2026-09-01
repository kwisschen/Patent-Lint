// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025-2026 Christopher Chen
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import '@fontsource-variable/geist'
import './i18n'
import './index.css'
import App from './App.jsx'
import { InfoTooltipProvider } from './components/ui/info-tooltip'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <InfoTooltipProvider>
        <App />
      </InfoTooltipProvider>
    </BrowserRouter>
  </StrictMode>,
)
