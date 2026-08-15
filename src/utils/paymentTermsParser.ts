export type PaymentTermsTrigger =
  | 'ACCEPTANCE_COMPLETED'
  | 'FIRST_AUDIT_COMPLETED'
  | 'FINAL_AUDIT_COMPLETED'
  | 'WARRANTY_EXPIRED'

export type PaymentTermsBaseType =
  | 'CONTRACT_PAYMENT_BASE'
  | 'FIRST_AUDIT_AMOUNT'
  | 'FINAL_AUDIT_AMOUNT'

export interface PaymentTermsNodeSuggestion {
  nodeName: string
  triggerCondition: PaymentTermsTrigger
  baseType: PaymentTermsBaseType
  paymentRatio: number
  isCumulative: boolean
  evidence: string
}

export interface PaymentTermsParseResult {
  nodes: PaymentTermsNodeSuggestion[]
  warnings: string[]
  confidence: 'high' | 'medium' | 'low'
}

type Candidate = PaymentTermsNodeSuggestion & { index: number; explicitCumulative: boolean }

const percentagePattern = /(\d+(?:\.\d+)?)\s*%/g

function contextAround(text: string, index: number, length: number) {
  const before = text.slice(Math.max(0, index - 42), index + length)
  const after = text.slice(index + length, Math.min(text.length, index + length + 18))
  return { before, after, text: `${before}${after}` }
}

function classify(before: string, after: string): Pick<PaymentTermsNodeSuggestion, 'nodeName' | 'triggerCondition' | 'baseType'> | null {
  if (/(质保|保修|缺陷责任期)/.test(before) || (/(剩余|余款)/.test(before) && /(质保|保修)/.test(after))) {
    return { nodeName: '质保期满后退还', triggerCondition: 'WARRANTY_EXPIRED', baseType: 'FINAL_AUDIT_AMOUNT' }
  }
  const stageMatches = [...before.matchAll(/二审|政府审计|终审|结算审计|定案|审定完成|最终审定|一审|竣工|验收|完工|项目完成|完成后/g)]
  const stageMatch = stageMatches.length ? stageMatches[stageMatches.length - 1][0] : ''
  if (stageMatch === '一审') {
    return { nodeName: '一审完成后付款', triggerCondition: 'FIRST_AUDIT_COMPLETED', baseType: 'FIRST_AUDIT_AMOUNT' }
  }
  if (/(二审|政府审计|终审|结算审计|定案|审定完成|最终审定)/.test(stageMatch)) {
    return { nodeName: '二审/政府审计/定案后付款', triggerCondition: 'FINAL_AUDIT_COMPLETED', baseType: 'FINAL_AUDIT_AMOUNT' }
  }
  if (stageMatch) {
    return { nodeName: '竣工验收后付款', triggerCondition: 'ACCEPTANCE_COMPLETED', baseType: 'CONTRACT_PAYMENT_BASE' }
  }
  return null
}

function normalizedTerms(input: string) {
  return input.replace(/[％﹪]/g, '%').replace(/[\r\n]+/g, '；').trim()
}

export function parsePaymentTerms(input: string): PaymentTermsParseResult {
  const text = normalizedTerms(input)
  if (!text) return { nodes: [], warnings: [], confidence: 'low' }

  const candidates: Candidate[] = []
  const warnings: string[] = []
  let match: RegExpExecArray | null
  percentagePattern.lastIndex = 0
  while ((match = percentagePattern.exec(text))) {
    const ratio = Number(match[1]) / 100
    if (ratio <= 0 || ratio > 1) {
      warnings.push(`比例 ${match[1]}% 超出 0% 至 100% 范围，未生成付款节点。`)
      continue
    }
    const context = contextAround(text, match.index, match[0].length)
    const classification = classify(context.before, context.after)
    if (!classification) {
      warnings.push(`未能判断 ${match[1]}% 对应的付款阶段，请人工核对。`)
      continue
    }
    candidates.push({
      ...classification,
      paymentRatio: ratio,
      isCumulative: false,
      evidence: context.text.replace(/；/g, ' '),
      index: match.index,
      explicitCumulative: /(付至|支付至|累计|达到|审定价的|按审定价)/.test(context.text),
    })
  }

  if (!candidates.length) {
    return {
      nodes: [],
      warnings: warnings.length ? warnings : ['暂未识别出带百分比的付款节点，请在第 5 步选择模板或手工录入。'],
      confidence: 'low',
    }
  }

  const paymentCandidates = candidates.filter((item) => item.triggerCondition !== 'WARRANTY_EXPIRED')
  const hasRetention = candidates.some((item) => item.triggerCondition === 'WARRANTY_EXPIRED')
  const progressive = paymentCandidates.every((item, index) => index === 0 || item.paymentRatio >= paymentCandidates[index - 1].paymentRatio)
  const lastPaymentCandidate = paymentCandidates[paymentCandidates.length - 1]
  const inferredCumulative = progressive && paymentCandidates.length > 1 && (hasRetention || lastPaymentCandidate.paymentRatio >= 0.8)

  const nodes = candidates
    .sort((left, right) => left.index - right.index)
    .map(({ index: _index, explicitCumulative, ...item }) => ({
      ...item,
      isCumulative: item.triggerCondition !== 'WARRANTY_EXPIRED' && (explicitCumulative || inferredCumulative),
    }))

  if (inferredCumulative && !candidates.every((item) => item.explicitCumulative || item.triggerCondition === 'WARRANTY_EXPIRED')) {
    warnings.push('部分条款未明确写出“累计支付”，系统根据比例递增顺序推断为累计节点，请重点核对。')
  }
  if (!inferredCumulative && candidates.some((item) => !item.explicitCumulative && item.triggerCondition !== 'WARRANTY_EXPIRED')) {
    warnings.push('部分条款未明确比例是单节点支付还是累计支付，请人工核对付款口径。')
  }
  if (warnings.length) warnings.push('识别结果仅作为付款节点草稿，确认生成前请逐项对照合同原文。')

  return { nodes, warnings, confidence: warnings.length ? 'medium' : 'high' }
}
