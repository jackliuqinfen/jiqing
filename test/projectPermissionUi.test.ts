import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const desktopSource = readFileSync(new URL('../src/views/ProjectManagementView.vue', import.meta.url), 'utf8')
const mobileSource = readFileSync(new URL('../src/views/MobileProjectManagementView.vue', import.meta.url), 'utf8')
const lifecycleSource = readFileSync(new URL('../src/components/project/ProjectLifecycleStatus.vue', import.meta.url), 'utf8')

test('lifecycle advancement is opt-in and both project views bind it to editor access', () => {
  assert.match(lifecycleSource, /canAdvance\?: boolean/)
  assert.match(lifecycleSource, /canAdvance: false/)
  assert.match(lifecycleSource, /snapshot\.nextTransition && props\.canAdvance/)
  assert.match(desktopSource, /:can-advance="authStore\.isEditor"/)
  assert.match(mobileSource, /:can-advance="authStore\.isEditor"/)
})

test('project deletion is administrator-only in the desktop view', () => {
  assert.match(desktopSource, /const canDelete = computed\(\(\) => authStore\.isAdmin\)/)
  assert.match(desktopSource, /if \(canDelete\.value\)/)
  assert.match(desktopSource, /if \(!requireAdminAccess\('删除项目'\)\) return/)
  assert.match(desktopSource, /if \(!requireAdminAccess\('删除资料'\)\) return/)
})

test('desktop and mobile mutation handlers defend editor-only actions', () => {
  for (const source of [desktopSource, mobileSource]) {
    assert.match(source, /function requireEditorAccess\(action: string\)/)
    assert.match(source, /if \(!requireEditorAccess\('上传资料'\)\) return/)
    assert.match(source, /if \(!requireEditorAccess\('发起审计'\)\) return/)
    assert.match(source, /if \(!requireEditorAccess\('推进项目阶段'\)\) return/)
  }
})

test('viewer-facing templates hide project mutation commands', () => {
  assert.match(desktopSource, /v-if="authStore\.isEditor" theme="primary" @click="openProjectForm\(\)"/)
  assert.match(desktopSource, /v-if="authStore\.isEditor" type="button" @click="openProjectForm\(row\)"/)
  assert.match(desktopSource, /v-if="canDelete" type="button" @click="confirmDeleteProject\(row\)"/)
  assert.match(mobileSource, /v-if="authStore\.isEditor" size="small" theme="primary" @click="openFileDialog\(\)"/)
  assert.match(mobileSource, /v-if="authStore\.isEditor" class="status-edit"/)
})
