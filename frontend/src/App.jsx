import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Loader2 } from 'lucide-react'
import Header from './components/Header'
import DropZone from './components/DropZone'
import AnalysisReport from './components/AnalysisReport'
import { analyzeDocument, downloadReport } from './api'

function App() {
  const { t } = useTranslation()
  const [state, setState] = useState('idle')
  const [result, setResult] = useState(null)
  const [file, setFile] = useState(null)
  const [error, setError] = useState(null)
  const [downloading, setDownloading] = useState(false)

  const handleFile = async (uploadedFile) => {
    setFile(uploadedFile)
    setError(null)
    setState('analyzing')

    try {
      const data = await analyzeDocument(uploadedFile)
      setResult(data)
      setState('results')
    } catch (err) {
      setError(err.message)
      setState('idle')
    }
  }

  const handleDownloadPdf = async () => {
    if (!file) return
    setDownloading(true)
    try {
      await downloadReport(file)
    } catch (err) {
      setError(err.message)
    } finally {
      setDownloading(false)
    }
  }

  const handleReset = () => {
    setState('idle')
    setResult(null)
    setFile(null)
    setError(null)
  }

  const year = new Date().getFullYear()

  return (
    <div className="min-h-screen flex flex-col">
      <Header onReset={handleReset} canReset={state !== 'idle'} />
      <main className="flex-1 mx-auto w-full max-w-5xl px-4 py-8">
        {state === 'idle' && (
          <div className="flex flex-col items-center justify-center min-h-[60vh]">
            <DropZone onFile={handleFile} />
          </div>
        )}

        {state === 'analyzing' && (
          <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            <p className="text-sm text-muted-foreground">{t('analysis.analyzing')}</p>
          </div>
        )}

        {state === 'results' && result && (
          <AnalysisReport
            data={result}
            filename={file?.name}
            onDownloadPdf={handleDownloadPdf}
            onReset={handleReset}
            downloading={downloading}
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
      </main>
      <footer className="border-t py-4 text-center text-xs text-muted-foreground">
        PatentLint &middot; {t('footer.disclaimer')} &middot; &copy; 2025-{year} Christopher Chen
      </footer>
    </div>
  )
}

export default App
