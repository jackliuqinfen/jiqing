<template>
  <div class="admin-users">
    <div class="page-header">
      <div class="page-header-left">
        <h2 class="page-title">用户管理</h2>
        <p class="page-desc">管理系统用户账号、角色和权限</p>
      </div>
      <t-button theme="primary" @click="openCreate">
        <template #icon><t-icon name="add" /></template>
        添加用户
      </t-button>
    </div>

    <!-- 搜索工具栏 -->
    <div class="user-toolbar">
      <t-input
        v-model="searchKeyword"
        placeholder="搜索用户名或姓名"
        clearable
        :style="{ width: '260px' }"
      >
        <template #prefix-icon><t-icon name="search" /></template>
      </t-input>
      <t-select
        v-model="roleFilter"
        placeholder="角色筛选"
        clearable
        :style="{ width: '130px' }"
        :options="roleOptions"
      />
      <span class="user-count">共 {{ filteredUsers.length }} 人</span>
    </div>

    <!-- 用户表格 — 无 stripe，纯边框 -->
    <t-table
      :data="filteredUsers"
      :columns="tableColumns"
      row-key="id"
      :loading="loading"
      :bordered="true"
      hover
      size="medium"
    >
      <template #username="{ row }">
        <span class="username-cell">{{ row.username }}</span>
      </template>
      <template #role="{ row }">
        <t-tag :theme="roleTheme(row.role)" variant="light" size="small">
          {{ roleLabel(row.role) }}
        </t-tag>
      </template>
      <template #isActive="{ row }">
        <t-tag :theme="row.isActive ? 'success' : 'default'" variant="light" size="small">
          {{ row.isActive ? '启用' : '禁用' }}
        </t-tag>
      </template>
      <template #createdAt="{ row }">
        <span class="date-cell">{{ formatDate(row.createdAt) }}</span>
      </template>
      <template #operation="{ row }">
        <t-space size="small">
          <t-button variant="text" size="small" theme="primary" @click="openEdit(row)">编辑</t-button>
          <t-popconfirm
            :content="row.isActive ? '确定禁用该用户？' : '确定启用该用户？'"
            @confirm="toggleUser(row)"
          >
            <t-button variant="text" size="small" :theme="row.isActive ? 'warning' : 'success'">
              {{ row.isActive ? '禁用' : '启用' }}
            </t-button>
          </t-popconfirm>
        </t-space>
      </template>
    </t-table>

    <!-- 添加/编辑弹窗 -->
    <t-dialog
      v-model:visible="modalVisible"
      :header="modalMode === 'create' ? '添加用户' : '编辑用户'"
      :confirm-btn="{ content: modalMode === 'create' ? '创建' : '保存', loading: modalLoading }"
      :close-on-overlay-click="false"
      width="480px"
      @confirm="handleSubmit"
    >
      <t-form ref="formRef" :data="formData" :rules="formRules" label-align="left" label-width="72px">
        <t-form-item label="账号" name="username">
          <t-input v-model="formData.username" placeholder="登录账号" :disabled="modalMode === 'edit'" />
        </t-form-item>
        <t-form-item label="姓名" name="displayName">
          <t-input v-model="formData.displayName" placeholder="真实姓名" />
        </t-form-item>
        <t-form-item label="邮箱" name="email">
          <t-input v-model="formData.email" placeholder="用于密码找回" />
        </t-form-item>
        <t-form-item v-if="modalMode === 'create'" label="密码" name="password">
          <t-input v-model="formData.password" type="password" placeholder="请输入密码" />
        </t-form-item>
        <t-form-item label="角色" name="role">
          <t-select v-model="formData.role" :options="roleOptions" placeholder="选择角色" />
        </t-form-item>
      </t-form>
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { getAdminUsers, updateAdminUser, signUpWithProfile } from '@/api/system'
import { MessagePlugin } from '@/ui/message'
import type { AdminUser, AdminRole, CreateAdminUserDto, UpdateAdminUserDto } from '@/types'
import type { FormInstanceFunctions, FormRule } from '@/ui/tdesignCompat'

const tableColumns = [
  { colKey: 'username', title: '账号', width: 130 },
  { colKey: 'displayName', title: '姓名', width: 110 },
  { colKey: 'email', title: '邮箱', ellipsis: true },
  { colKey: 'role', title: '角色', width: 90 },
  { colKey: 'isActive', title: '状态', width: 70 },
  { colKey: 'createdAt', title: '创建时间', width: 130 },
  { colKey: 'operation', title: '操作', width: 130, fixed: 'right' },
]

const roleOptions = [
  { label: '管理员', value: 'admin' },
  { label: '编辑者', value: 'editor' },
  { label: '查看者', value: 'viewer' },
]

function roleLabel(role: AdminRole): string {
  return { admin: '管理员', editor: '编辑者', viewer: '查看者' }[role] ?? role
}

function roleTheme(role: AdminRole): string {
  return { admin: 'danger', editor: 'warning', viewer: 'primary' }[role] ?? 'default'
}

function formatDate(iso: string): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
}

const users = ref<AdminUser[]>([])
const loading = ref(false)
const searchKeyword = ref('')
const roleFilter = ref<AdminRole | ''>('')

const filteredUsers = computed(() => {
  let list = users.value
  if (searchKeyword.value) {
    const kw = searchKeyword.value.toLowerCase()
    list = list.filter(u => u.username.toLowerCase().includes(kw) || u.displayName.toLowerCase().includes(kw))
  }
  if (roleFilter.value) list = list.filter(u => u.role === roleFilter.value)
  return list
})

async function fetchUsers() {
  loading.value = true
  try { users.value = await getAdminUsers() }
  catch { MessagePlugin.error('获取用户列表失败') }
  finally { loading.value = false }
}

onMounted(fetchUsers)

const modalVisible = ref(false)
const modalMode = ref<'create' | 'edit'>('create')
const modalLoading = ref(false)
const editingUserId = ref<string | null>(null)
const formRef = ref<FormInstanceFunctions | null>(null)

const formData = reactive<CreateAdminUserDto & { id?: string }>({
  username: '', displayName: '', email: '', password: '', role: 'viewer',
})

const formRules: Record<string, FormRule[]> = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }, { min: 2, max: 50, message: '2-50 个字符', trigger: 'blur' }],
  displayName: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  email: [{ required: true, message: '请输入邮箱', trigger: 'blur' }, { email: true, message: '邮箱格式不正确', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  role: [{ required: true, message: '请选择', trigger: 'change' }],
}

function resetForm() {
  formData.username = ''; formData.displayName = ''; formData.email = ''
  formData.password = ''; formData.role = 'viewer'; editingUserId.value = null
}

function openCreate() { modalMode.value = 'create'; resetForm(); modalVisible.value = true }

function openEdit(user: AdminUser) {
  modalMode.value = 'edit'; editingUserId.value = user.id
  formData.id = user.id; formData.username = user.username
  formData.displayName = user.displayName; formData.email = user.email
  formData.password = ''; formData.role = user.role
  modalVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value?.validate()
  if (valid !== true) return
  modalLoading.value = true
  try {
    if (modalMode.value === 'create') {
      await signUpWithProfile({
        username: formData.username, displayName: formData.displayName,
        email: formData.email, password: formData.password, role: formData.role,
      })
      MessagePlugin.success('用户创建成功')
    } else {
      const dto: UpdateAdminUserDto = {
        id: editingUserId.value!,
        displayName: formData.displayName, email: formData.email, role: formData.role,
      }
      if (formData.password) dto.password = formData.password
      await updateAdminUser(dto)
      MessagePlugin.success('用户信息已更新')
    }
    modalVisible.value = false
    await fetchUsers()
  } catch (err) { MessagePlugin.error(err instanceof Error ? err.message : '操作失败') }
  finally { modalLoading.value = false }
}

async function toggleUser(user: AdminUser) {
  try {
    await updateAdminUser({ id: user.id, isActive: !user.isActive })
    MessagePlugin.success(user.isActive ? '用户已禁用' : '用户已启用')
    await fetchUsers()
  } catch (err) { MessagePlugin.error(err instanceof Error ? err.message : '操作失败') }
}
</script>

<style scoped>
.admin-users { max-width: 1100px; }

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: var(--space-6);
}

.page-header-left { min-width: 0; }
.page-title { font-size: var(--text-2xl); font-weight: 700; color: var(--text-primary); margin: 0 0 var(--space-1); }
.page-desc { font-size: var(--text-sm); color: var(--text-secondary); margin: 0; }

.user-toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
  padding: var(--space-3);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
}

.user-count { margin-left: auto; font-size: var(--text-xs); color: var(--text-tertiary); }
.username-cell { font-weight: 500; }
.date-cell { font-size: var(--text-xs); color: var(--text-secondary); }
</style>
