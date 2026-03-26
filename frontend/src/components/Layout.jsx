// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025 Christopher Chen
import { useLocation } from 'react-router-dom'
import Header from './Header'
import Footer from './Footer'

export default function Layout({ children, onReset, canReset }) {
  const location = useLocation()

  return (
    <div className="min-h-screen flex flex-col">
      <Header onReset={onReset} canReset={canReset} />
      <main className="flex-1">
        <div key={location.pathname} className="page-enter-active">
          {children}
        </div>
      </main>
      <Footer />
    </div>
  )
}
