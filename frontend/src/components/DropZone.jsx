import { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload } from 'lucide-react'
import { useTranslation } from 'react-i18next'

export default function DropZone({ onFile }) {
  const { t } = useTranslation()

  const onDrop = useCallback((acceptedFiles) => {
    if (acceptedFiles.length > 0) {
      onFile(acceptedFiles[0])
    }
  }, [onFile])

  const { getRootProps, getInputProps, isDragActive, fileRejections } = useDropzone({
    onDrop,
    accept: {
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    },
    maxFiles: 1,
  })

  return (
    <div className="flex flex-col items-center gap-3">
      <div
        {...getRootProps()}
        className={`
          flex flex-col items-center justify-center gap-4
          w-full max-w-lg p-12 rounded-lg
          border-2 border-dashed cursor-pointer
          transition-colors duration-200
          ${isDragActive
            ? 'border-[var(--pass-border)] bg-[var(--pass-bg)]/30'
            : 'border-border hover:border-muted-foreground/50'
          }
        `}
      >
        <input {...getInputProps()} />
        <Upload className={`h-10 w-10 ${isDragActive ? 'text-[var(--pass-text)]' : 'text-muted-foreground'}`} />
        <div className="text-center">
          <p className="text-base font-medium">{t('dropzone.title')}</p>
          <p className="text-sm text-muted-foreground mt-1">{t('dropzone.subtitle')}</p>
          <p className="text-xs text-muted-foreground mt-2">{t('dropzone.notice')}</p>
        </div>
      </div>
      {fileRejections.length > 0 && (
        <p className="text-sm text-[var(--amend-text)]">
          {t('dropzone.reject')}
        </p>
      )}
    </div>
  )
}
