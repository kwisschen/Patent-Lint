import { describe, expect, it } from 'vitest'
import { excerptAround } from '../lib/feedback.js'

// Report #809: spec-support phrases arrive lowercased, so a claim reciting an
// acronym never matched and the report carried no context. Synthetic text.
describe('excerptAround', () => {
  const claim = 'The circuit of claim 1, wherein the logic block comprises a logical NAND gate coupled to the output.'

  it('finds a lowercased phrase in original-cased claim text', () => {
    const r = excerptAround(claim, 'logical nand')
    expect(r.char_offset).toBe(claim.indexOf('logical NAND'))
    expect(r.context_before.endsWith('comprises a ')).toBe(true)
    expect(r.context_after.startsWith(' gate coupled')).toBe(true)
  })

  it('still prefers an exact match when one exists', () => {
    const text = 'a Data bus and a data bus'
    expect(excerptAround(text, 'data bus').char_offset).toBe(text.lastIndexOf('data bus'))
  })

  it('returns all-null when the phrase is absent in any case', () => {
    expect(excerptAround(claim, 'flip flop')).toEqual({ context_before: null, context_after: null, char_offset: null })
  })
})
