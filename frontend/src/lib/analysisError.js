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
  const key = `error.input.${code}`
  const localized = t(key)
  // i18next echoes the key back when it has no translation for it.
  if (localized && localized !== key) return localized
  return englishFallback || message
}
