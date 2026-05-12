// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025–2026 Christopher Chen
import { useState, useCallback, useEffect } from 'react'
import { Routes, Route } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Loader2 } from 'lucide-react'
import Layout from './components/Layout'
import DropZone from './components/DropZone'
import AnalysisReport from './components/AnalysisReport'
import ScannedDocBanner from './components/ScannedDocBanner'
import LoadingOnboard from './components/LoadingOnboard'
import ProveItModal from './components/ProveItModal'
import NetworkWidget from './components/NetworkWidget'
import { FeedbackProvider } from './components/FeedbackPicker'
import SecurityPage from './pages/SecurityPage'
import AboutPage from './pages/AboutPage'
import CommercialPage from './pages/CommercialPage'
import TermsPage from './pages/TermsPage'
import PrivacyPage from './pages/PrivacyPage'
import RubricPage from './pages/RubricPage'
import { usePyodide } from './hooks/usePyodide'
import { useUpdateCheck } from './hooks/useUpdateCheck'
import { Toaster } from './components/ui/sonner'
import { downloadReport as downloadReportClient } from './lib/pdfExport'
import { preloadMermaidChunks } from './lib/preloadMermaid'
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

  // Pre-load mermaid's flowchart chunks during the initial loading
  // phase so they don't lazy-load (and burst into DevTools' Network
  // tab) the first time AnalysisReport renders the claim tree. See
  // lib/preloadMermaid.js for the full rationale.
  useEffect(() => {
    preloadMermaidChunks()
  }, [])

  // Home page state
  const [jurisdiction, setJurisdiction] = useState('US')

  // Note: CJK font (Noto Sans TC/SC/JP/KR) is no longer prefetched
  // at App mount. The fetch was a ~1MB GET to fonts.gstatic.com that
  // appeared in DevTools' Network tab as if triggered by the user's
  // drop event (the entry was actually from page load, but the user
  // typically opens DevTools after dropping, so the timing read as
  // "PatentLint just touched the network when I gave it my draft").
  // The font is only consumed by PDF export. loadCjkFont in pdfExport.js
  // handles on-demand fetching the first time the user clicks Download
  // PDF — covered by the existing "Generating..." button state. Cached
  // module-level after first download, so subsequent clicks are instant.
  const [homeState, setHomeState] = useState('idle')
  const [result, setResult] = useState(null)
  const [file, setFile] = useState(null)
  const [error, setError] = useState(null)
  const [downloading, setDownloading] = useState(false)

  // ``jurisdictionOverride`` lets the JurisdictionMismatchBanner re-run
  // analysis on the same already-loaded file under a different
  // jurisdiction without forcing the user to re-upload. When provided
  // we also commit the new jurisdiction to App state so the picker
  // reflects what was actually analyzed.
  const handleFile = async (uploadedFile, jurisdictionOverride) => {
    setFile(uploadedFile)
    setError(null)
    setHomeState('analyzing')

    const jurisdictionForRun = jurisdictionOverride || jurisdiction
    if (jurisdictionOverride && jurisdictionOverride !== jurisdiction) {
      setJurisdiction(jurisdictionOverride)
    }

    try {
      if (!pyodide.ready) {
        throw new Error(t('analysis.engineNotReady'))
      }
      const data = await pyodide.analyze(uploadedFile, jurisdictionForRun)
      setResult(data)
      setHomeState('results')
    } catch (err) {
      setError(err.message)
      setHomeState('idle')
    }
  }

  const handleDownloadPdf = async () => {
    if (!file || !pyodide.ready || !result) return
    setDownloading(true)
    try {
      await downloadReportClient(result, t, i18n.language, file.name)
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
                  <div
                    className="grid grid-cols-2 sm:grid-cols-4 gap-1 rounded-lg p-1 mt-3 mb-4 ring-1 w-full max-w-md sm:max-w-xl mx-auto"
                    style={{
                      backgroundImage: 'var(--frost-resting-bg)',
                      boxShadow: 'var(--frost-resting-inner-light)',
                      borderColor: 'var(--frost-resting-border)',
                    }}
                    role="radiogroup"
                    aria-label={t('jurisdiction.label')}
                  >
                    {['US', 'CN', 'TW', 'EPC'].map((j) => (
                      <button
                        key={j}
                        role="radio"
                        aria-checked={jurisdiction === j}
                        onClick={() => setJurisdiction(j)}
                        className={`flex items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-sm font-medium transition-all duration-[var(--motion-duration-fast)] ${
                          jurisdiction === j
                            ? 'bg-card text-foreground shadow-md ring-1 ring-foreground/15'
                            : 'text-muted-foreground hover:text-foreground hover:bg-card/40'
                        }`}
                      >
                        <JurisdictionBadge code={j} />
                        <span className="truncate">{t(`jurisdiction.${j.toLowerCase()}`)}</span>
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
                    onSwitchJurisdiction={(target) => handleFile(file, target)}
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
          <Route path="/rubric" element={<RubricPage />} />
          <Route path="/commercial" element={<CommercialPage />} />
        </Routes>
      </Layout>

      <NetworkWidget pyodideReady={pyodide.ready} />
      <ProveItModal open={showProveIt} onOpenChange={setShowProveIt} />
      <Toaster />
    </FeedbackProvider>
  )
}

export default App
