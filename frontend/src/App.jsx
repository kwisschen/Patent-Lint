// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025 Christopher Chen
import { useState, useCallback, useEffect } from 'react'
import { Routes, Route } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Loader2 } from 'lucide-react'
import Layout from './components/Layout'
import DropZone from './components/DropZone'
import BetaBadge from './components/BetaBadge'
import AnalysisReport from './components/AnalysisReport'
import ScannedDocBanner from './components/ScannedDocBanner'
import LoadingOnboard from './components/LoadingOnboard'
import ProveItModal from './components/ProveItModal'
import { FeedbackProvider } from './components/FeedbackPicker'
import SecurityPage from './pages/SecurityPage'
import AboutPage from './pages/AboutPage'
import TermsPage from './pages/TermsPage'
import PrivacyPage from './pages/PrivacyPage'
import { usePyodide } from './hooks/usePyodide'
import { useUpdateCheck } from './hooks/useUpdateCheck'
import { Toaster } from './components/ui/sonner'
import { analyzeDocument, downloadReport as downloadReportServer } from './api'
import { downloadReport as downloadReportClient, prefetchCjkFont } from './lib/pdfExport'
import { getJurisdictionConfig, JURISDICTION_COLORS } from './lib/jurisdictionConfig'
import { CHECKS_BY_JURISDICTION } from './generated/stats'

function JurisdictionBadge({ code }) {
  return (
    <span
      className="inline-flex items-center justify-center w-5 h-5 sm:w-6 sm:h-6 rounded-full text-[8px] sm:text-[9px] font-bold text-white shrink-0"
      style={{ backgroundColor: JURISDICTION_COLORS[code] }}
    >
      {code}
    </span>
  )
}

function App() {
  const { t, i18n } = useTranslation()
  useUpdateCheck()
  const pyodide = usePyodide()
  const [engineReady, setEngineReady] = useState(false)
  const [showProveIt, setShowProveIt] = useState(false)

  const handleEngineReady = useCallback(() => {
    setEngineReady(true)
  }, [])

  useEffect(() => {
    prefetchCjkFont(i18n.language)
  }, [i18n.language])

  // Home page state
  const [jurisdiction, setJurisdiction] = useState('US')

  // Prefetch CJK font for jurisdiction (CN/TW content always contains CJK)
  useEffect(() => {
    const jConfig = getJurisdictionConfig(jurisdiction)
    if (jConfig.cjkFont) {
      prefetchCjkFont(jConfig.cjkFont)
    }
  }, [jurisdiction])
  const [homeState, setHomeState] = useState('idle')
  const [result, setResult] = useState(null)
  const [file, setFile] = useState(null)
  const [error, setError] = useState(null)
  const [downloading, setDownloading] = useState(false)

  const handleFile = async (uploadedFile) => {
    setFile(uploadedFile)
    setError(null)
    setHomeState('analyzing')

    try {
      let data
      if (pyodide.ready) {
        data = await pyodide.analyze(uploadedFile, jurisdiction)
      } else {
        data = await analyzeDocument(uploadedFile, jurisdiction)
      }
      setResult(data)
      setHomeState('results')
    } catch (err) {
      setError(err.message)
      setHomeState('idle')
    }
  }

  const handleDownloadPdf = async () => {
    if (!file) return
    setDownloading(true)
    try {
      if (pyodide.ready && result) {
        await downloadReportClient(result, t, i18n.language, file.name)
      } else {
        await downloadReportServer(file)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setDownloading(false)
    }
  }

  const handleReset = useCallback(() => {
    setHomeState('idle')
    setResult(null)
    setFile(null)
    setError(null)
  }, [])

  useEffect(() => {
    if (homeState === 'results') {
      window.history.pushState({ patentlint: 'results' }, '')
    }
  }, [homeState])

  useEffect(() => {
    const handlePopState = (e) => {
      if (homeState === 'results') {
        handleReset()
      }
    }
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [homeState, handleReset])

  return (
    <FeedbackProvider>
      {!engineReady && !pyodide.error && (
        <LoadingOnboard progress={pyodide.progress} onReady={handleEngineReady} />
      )}

      <Layout onReset={handleReset} canReset={homeState !== 'idle'} hasActionBar={homeState === 'results'}>
        <Routes>
          <Route path="/" element={
            <div className="mx-auto w-full max-w-5xl px-4 py-8">
              {homeState === 'idle' && (
                <div className="flex flex-col items-center justify-center min-h-[40vh] sm:min-h-[60vh]">
                  <div className="flex items-center justify-center gap-1 rounded-lg bg-muted p-1 mt-3 mb-4" role="radiogroup" aria-label={t('jurisdiction.label')}>
                    {['US', 'CN', 'TW'].map((j) => (
                      <button
                        key={j}
                        role="radio"
                        aria-checked={jurisdiction === j}
                        onClick={() => setJurisdiction(j)}
                        className={`relative flex items-center gap-1 sm:gap-1.5 rounded-md px-2 sm:px-3 py-1 sm:py-1.5 text-xs sm:text-sm font-medium whitespace-nowrap transition-colors ${
                          jurisdiction === j
                            ? 'bg-background text-foreground shadow-sm'
                            : 'text-muted-foreground hover:text-foreground'
                        }`}
                      >
                        <JurisdictionBadge code={j} />
                        {t(`jurisdiction.${j.toLowerCase()}`)}
                        {j === 'CN' && (
                          <span className="absolute -top-2 right-0 pointer-events-none">
                            <BetaBadge />
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                  <p className="text-base sm:text-lg text-muted-foreground text-center mb-4">{t(getJurisdictionConfig(jurisdiction).taglineKey, { count: CHECKS_BY_JURISDICTION[jurisdiction] })}</p>
                  <DropZone onFile={handleFile} onShowProveIt={() => setShowProveIt(true)} jurisdiction={jurisdiction} />
                </div>
              )}

              {homeState === 'analyzing' && (
                <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">{t('analysis.analyzing')}</p>
                </div>
              )}

              {homeState === 'results' && result && (
                result.has_scanned_fallback ? (
                  <ScannedDocBanner onReset={handleReset} />
                ) : (
                  <AnalysisReport
                    data={result}
                    filename={file?.name}
                    onDownloadPdf={handleDownloadPdf}
                    onReset={handleReset}
                    downloading={downloading}
                    onShowProveIt={() => setShowProveIt(true)}
                    pyodideReady={pyodide.ready}
                  />
                )
              )}

              {error && (
                <div className="mt-4 rounded-lg border p-4 text-sm" style={{
                  borderColor: 'var(--amend-border)',
                  backgroundColor: 'var(--amend-bg)',
                  color: 'var(--amend-text)',
                }}>
                  {error}
                </div>
              )}
            </div>
          } />
          <Route path="/security" element={
            <div className="mx-auto w-full max-w-5xl px-4 py-8">
              <SecurityPage onShowProveIt={() => setShowProveIt(true)} />
            </div>
          } />
          <Route path="/about" element={
            <div className="mx-auto w-full max-w-5xl px-4 py-8">
              <AboutPage />
            </div>
          } />
          <Route path="/terms" element={<TermsPage />} />
          <Route path="/privacy" element={<PrivacyPage />} />
        </Routes>
      </Layout>

      <ProveItModal open={showProveIt} onOpenChange={setShowProveIt} />
      <Toaster />
    </FeedbackProvider>
  )
}

export default App
