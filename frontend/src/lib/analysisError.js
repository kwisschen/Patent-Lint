// SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
// Copyright (c) 2025–2026 Christopher Chen

/**
 * Maps engine input-format errors onto localized, actionable copy.
 *
 * The Python layer raises UnsupportedInputError (see
 * src/patentlint/parser/file_format.py) whose string form is
 * `PL_ERR:<code>|<english fallback>`. Pyodide surfaces that inside a full
 * Python traceback, so the code is searched for anywhere in the message
 * rather than matched at the start.
 *
 * Unknown codes and non-format errors fall through to the raw message, so
 * this never swallows an error it does not recognise.
 */

const ERROR_CODE_RE = /PL_ERR:([a-z_]+)\|([^\n]*)/

/**
 * @param {string} message  raw error message from the analysis engine
 * @param {(key: string) => string} t  i18n translate function
 * @returns {string} localized copy when the error is a known input-format
 *   failure, otherwise the original message unchanged
 */
export function formatAnalysisError(message, t) {
  if (!message) return message
  const match = ERROR_CODE_RE.exec(message)
  if (!match) return message

  const [, code, englishFallback] = match
  const localized = translateCode(code, t)
  return localized || englishFallback || message
}

/**
 * Look up localized copy for an input-format code.
 * Returns null when the locale has no entry (i18next echoes the key back).
 */
function translateCode(code, t) {
  const key = `error.input.${code}`
  const localized = t(key)
  return localized && localized !== key ? localized : null
}

/**
 * Extension and MIME signatures for files a user plausibly drops by mistake.
 *
 * The engine sniffs magic bytes, but it only ever sees files that clear
 * react-dropzone's `accept` filter. A file with a genuine `.doc` extension
 * is rejected at the dropzone and never reaches Python, so without this the
 * single most likely mistake (dropping an actual legacy .doc) fell back to
 * the generic "Only .docx files are accepted".
 *
 * Codes match src/patentlint/parser/file_format.py so both paths render
 * identical copy from the same error.input.* keys.
 */
const REJECTED_FILE_SIGNATURES = [
  { code: 'legacy_doc', extensions: ['.doc'], mimeTypes: ['application/msword'] },
  { code: 'pdf_not_docx', extensions: ['.pdf'], mimeTypes: ['application/pdf'] },
  { code: 'rtf_not_docx', extensions: ['.rtf'], mimeTypes: ['application/rtf', 'text/rtf'] },
  {
    code: 'not_word_package',
    extensions: ['.pages', '.odt', '.xls', '.xlsx', '.ppt', '.pptx'],
    mimeTypes: [],
  },
]

/**
 * Localized reason a dropped file was rejected, based on what it appears to
 * be. Null when the file does not match a known mistake, so the caller keeps
 * its generic per-jurisdiction message.
 *
 * @param {File} file  the rejected file
 * @param {(key: string) => string} t  i18n translate function
 * @returns {string|null}
 */
export function describeRejectedFile(file, t) {
  if (!file) return null
  const name = (file.name || '').toLowerCase()
  const mime = (file.type || '').toLowerCase()

  const match = REJECTED_FILE_SIGNATURES.find(
    (sig) =>
      sig.extensions.some((ext) => name.endsWith(ext)) ||
      (mime && sig.mimeTypes.includes(mime)),
  )
  if (!match) return null
  return translateCode(match.code, t)
}
