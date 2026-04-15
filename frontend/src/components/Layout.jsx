// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2025 Christopher Chen
import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import Header from './Header'
import Footer from './Footer'

export default function Layout({ children, onReset, canReset, hasActionBar }) {
  const location = useLocation()

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [location.pathname])

  return (
    <div className="min-h-screen flex flex-col">
      <Header onReset={onReset} canReset={canReset} />
      <main className="flex-1">
        <div key={location.pathname} className="page-enter-active">
          {children}
        </div>
      </main>
      <div className={hasActionBar ? 'pb-16' : ''}><Footer /></div>
    </div>
  )
}
