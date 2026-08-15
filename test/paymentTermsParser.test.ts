import assert from 'node:assert/strict'
import test from 'node:test'

import { parsePaymentTerms } from '../src/utils/paymentTermsParser.ts'

test('recognizes common cumulative payment clauses and warranty retention', () => {
  const result = parsePaymentTerms('竣工验收合格后按合同价款的60%支付；一审后按审定价的70%支付；二审结束后按审定价的97%付款，剩余3%作为质保金。')

  assert.deepEqual(result.nodes.map((item) => [item.triggerCondition, item.paymentRatio, item.isCumulative]), [
    ['ACCEPTANCE_COMPLETED', 0.6, true],
    ['FIRST_AUDIT_COMPLETED', 0.7, true],
    ['FINAL_AUDIT_COMPLETED', 0.97, true],
    ['WARRANTY_EXPIRED', 0.03, false],
  ])
  assert.equal(result.confidence, 'high')
})

test('keeps ambiguous percentages visible for manual review', () => {
  const result = parsePaymentTerms('项目完成后支付80%，其余款项另行结算。')

  assert.equal(result.nodes.length, 1)
  assert.equal(result.nodes[0].triggerCondition, 'ACCEPTANCE_COMPLETED')
  assert.equal(result.confidence, 'medium')
  assert.ok(result.warnings.some((item) => item.includes('识别结果仅作为付款节点草稿')))
})

test('does not invent nodes when the clause has no recognizable percentage', () => {
  const result = parsePaymentTerms('付款按合同约定办理。')

  assert.equal(result.nodes.length, 0)
  assert.equal(result.confidence, 'low')
})
