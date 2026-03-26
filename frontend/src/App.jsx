// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025 Christopher Chen
import { useState, useCallback } from 'react'
import { Routes, Route } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Loader2 } from 'lucide-react'
import Layout from './components/Layout'
import DropZone from './components/DropZone'
import AnalysisReport from './components/AnalysisReport'
import LoadingOnboard from './components/LoadingOnboard'
import ProveItModal from './components/ProveItModal'
import SecurityPage from './pages/SecurityPage'
import AboutPage from './pages/AboutPage'
import { usePyodide } from './hooks/usePyodide'
import { analyzeDocument, downloadReport as downloadReportServer } from './api'
import { downloadReport as downloadReportClient } from './lib/pdfExport'

function App() {
  const { t, i18n } = useTranslation()
  const pyodide = usePyodide()
  const [engineReady, setEngineReady] = useState(false)
  const [showProveIt, setShowProveIt] = useState(false)

  const handleEngineReady = useCallback(() => {
    setEngineReady(true)
  }, [])

  // Home page state
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
        data = await pyodide.analyze(uploadedFile)
      } else {
        data = await analyzeDocument(uploadedFile)
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

  const handleReset = () => {
    setHomeState('idle')
    setResult(null)
    setFile(null)
    setError(null)
  }

  return (
    <>
      {!engineReady && !pyodide.error && (
        <LoadingOnboard progress={pyodide.progress} onReady={handleEngineReady} />
      )}

      <Layout onReset={handleReset} canReset={homeState !== 'idle'} hasActionBar={homeState === 'results'}>
        <Routes>
          <Route path="/" element={
            <div className="mx-auto w-full max-w-5xl px-4 py-8">
              {homeState === 'idle' && (
                <div className="flex flex-col items-center justify-center min-h-[60vh]">
                  <DropZone onFile={handleFile} onShowProveIt={() => setShowProveIt(true)} />
                </div>
              )}

              {homeState === 'analyzing' && (
                <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">{t('analysis.analyzing')}</p>
                </div>
              )}

              {homeState === 'results' && result && (
                <AnalysisReport
                  data={result}
                  filename={file?.name}
                  onDownloadPdf={handleDownloadPdf}
                  onReset={handleReset}
                  downloading={downloading}
                  onShowProveIt={() => setShowProveIt(true)}
                  pyodideReady={pyodide.ready}
                />
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
        </Routes>
      </Layout>

      <ProveItModal open={showProveIt} onOpenChange={setShowProveIt} />
    </>
  )
}

export default App
