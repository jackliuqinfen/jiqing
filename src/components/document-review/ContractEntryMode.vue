<template>
  <section class="entry-mode">
    <header>
      <span>手工创建项目</span>
      <h4>目前请手工填写合同与项目信息</h4>
      <p>填写内容可以保存为草稿，关联合同原件并人工确认后才会创建正式项目。</p>
    </header>
    <div class="entry-mode__grid">
      <button v-if="projectIntakeFeatures.systemRecognition" type="button" @click="$emit('select', 'system')">
        <small>推荐</small>
        <strong>系统 AI 识别</strong>
        <span>上传合同后自动解析并预填字段</span>
      </button>
      <button v-if="projectIntakeFeatures.externalAiImport" type="button" @click="$emit('select', 'external')">
        <small>无需 API</small>
        <strong>粘贴外部 AI 结果</strong>
        <span>复制提示词到豆包或 ChatGPT，再粘贴结果</span>
      </button>
      <button type="button" @click="$emit('select', 'manual')">
        <small>当前录入方式</small>
        <strong>手工录入项目</strong>
        <span>可以先填写并保存草稿，上传合同原件后进入复核</span>
      </button>
    </div>
    <section v-if="drafts.length || loading" class="draft-list">
      <header class="draft-list__head">
        <div><strong>未完成的合同草稿</strong><span>继续上次录入，正式建档前仍可修改或放弃。</span></div>
        <small>{{ loading ? '正在加载' : `${drafts.length} 条` }}</small>
      </header>
      <div v-if="drafts.length" class="draft-list__rows">
        <article v-for="draft in drafts" :key="draft.id">
          <div>
            <strong>{{ draftTitle(draft) }}</strong>
            <span>{{ draft.status === 'document_attached' ? '已关联合同原件' : '尚未关联合同原件' }} · {{ formatTime(draft.updatedAt) }}</span>
          </div>
          <div class="draft-list__actions">
            <AButton size="small" variant="outline" @click="$emit('abandon', draft.id)">放弃</AButton>
            <AButton size="small" theme="primary" @click="$emit('resume', draft)">继续填写</AButton>
          </div>
        </article>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import type { ProjectIntakeDraft } from '@/types/documentReview'
import { projectIntakeFeatures } from '@/config/projectIntakeFeatures'

defineProps<{ drafts: ProjectIntakeDraft[]; loading: boolean }>()
defineEmits<{
  select: [mode: 'system' | 'external' | 'manual']
  resume: [draft: ProjectIntakeDraft]
  abandon: [draftId: string]
}>()

function draftTitle(draft: ProjectIntakeDraft) {
  return String(draft.values['project.name'] || '').trim() || '未命名合同草稿'
}

function formatTime(value: string) {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return '时间待确认'
  return parsed.toLocaleString('zh-CN', { hour12: false })
}
</script>

<style scoped>
.entry-mode { width: min(900px, 100%); margin: 0 auto; }
.entry-mode header { margin-bottom: 22px; text-align: center; }
.entry-mode header > span { color: var(--primary-color); font-size: 12px; font-weight: 700; }
.entry-mode h4 { margin: 8px 0; font-size: 20px; }
.entry-mode p { margin: 0; color: var(--text-secondary); }
.entry-mode__grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.entry-mode__grid:has(> button:only-child) { width: min(440px, 100%); grid-template-columns: 1fr; margin-inline: auto; }
.entry-mode__grid button { min-height: 156px; display: grid; align-content: center; gap: 9px; padding: 24px; text-align: left; border: 1px solid var(--border-color); border-radius: var(--radius-lg, 8px); color: var(--text-primary); background: rgba(255,255,255,.88); cursor: pointer; transition: border-color .2s ease, box-shadow .2s ease, transform .2s ease; }
.entry-mode__grid button:hover { border-color: rgba(22,93,255,.45); box-shadow: 0 10px 28px rgba(50,82,130,.10); transform: translateY(-2px); }
.entry-mode__grid small { color: var(--primary-color); font-weight: 700; }
.entry-mode__grid strong { font-size: 17px; }
.entry-mode__grid span { color: var(--text-secondary); line-height: 1.6; }
.draft-list { display: grid; gap: 10px; margin-top: 20px; padding-top: 18px; border-top: 1px solid var(--border-color); }
.draft-list__head, .draft-list__rows article, .draft-list__actions { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.draft-list__head > div, .draft-list__rows article > div:first-child { display: grid; gap: 4px; }
.draft-list__head span, .draft-list__rows span, .draft-list__head small { color: var(--text-secondary); font-size: 12px; }
.draft-list__rows { display: grid; gap: 8px; }
.draft-list__rows article { min-height: 62px; padding: 10px 12px; border: 1px solid var(--border-color); border-radius: var(--radius-lg, 8px); background: rgba(255,255,255,.76); }
@media (max-width: 820px) { .entry-mode__grid { grid-template-columns: 1fr; } }
</style>
