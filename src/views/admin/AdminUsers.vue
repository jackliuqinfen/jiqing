<template>
  <div class="admin-users">
    <PageHeader title="用户管理" description="管理系统用户账号、角色和权限">
      <template #meta>
        <ATag variant="light" theme="primary">共 {{ filteredUsers.length }} 人</ATag>
        <ATag v-if="searchKeyword || roleFilter" variant="light">已应用筛选</ATag>
      </template>
      <template #actions>
        <AButton variant="outline" :loading="loading" @click="fetchUsers">
          <template #icon><AIcon name="refresh" /></template>
          刷新
        </AButton>
        <AButton theme="primary" @click="openCreate">
          <template #icon><AIcon name="add" /></template>
          添加用户
        </AButton>
      </template>
    </PageHeader>

    <div class="user-toolbar">
      <AInput
        v-model="searchKeyword"
        placeholder="搜索用户名或姓名"
        clearable
        :style="{ width: '260px' }"
      >
        <template #prefix-icon><AIcon name="search" /></template>
      </AInput>
      <ASelect
        v-model="roleFilter"
        placeholder="角色筛选"
        clearable
        :style="{ width: '130px' }"
        :options="roleOptions"
      />
      <span class="user-count">共 {{ filteredUsers.length }} 人</span>
    </div>

    <StatePanel
      v-if="loading && users.length === 0"
      state="loading"
      title="正在加载用户数据"
      description="系统正在读取当前可管理的账号信息，请稍候。"
    />

    <StatePanel
      v-else-if="fetchError"
      state="error"
      title="用户列表加载失败"
      description="刚才没有取到用户数据，可能是网络波动或服务暂时不可用。你可以重试，若仍失败请联系管理员。"
    >
      <template #actions>
        <AButton theme="primary" :loading="loading" @click="fetchUsers">
          <template #icon><AIcon name="refresh" /></template>
          重新加载
        </AButton>
      </template>
    </StatePanel>

    <StatePanel
      v-else-if="filteredUsers.length === 0"
      state="empty"
      title="未找到符合条件的用户"
      :description="searchKeyword || roleFilter ? '请调整筛选条件后再试，或直接清除筛选查看全部用户。' : '当前还没有可管理的用户账号。'"
    >
      <template #actions>
        <AButton v-if="searchKeyword || roleFilter" variant="outline" @click="resetFilters">清除筛选</AButton>
        <AButton theme="primary" @click="openCreate">
          <template #icon><AIcon name="add" /></template>
          添加用户
        </AButton>
      </template>
    </StatePanel>

    <ATable
      v-else
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
        <ATag :theme="roleTheme(row.role)" variant="light" size="small">
          {{ roleLabel(row.role) }}
        </ATag>
      </template>
      <template #isActive="{ row }">
        <ATag :theme="row.isActive ? 'success' : 'default'" variant="light" size="small">
          {{ row.isActive ? '启用' : '禁用' }}
        </ATag>
      </template>
      <template #createdAt="{ row }">
        <span class="date-cell">{{ formatDate(row.createdAt) }}</span>
      </template>
      <template #operation="{ row }">
        <div class="table-actions">
          <AButton variant="text" size="small" theme="primary" @click="openEdit(row)">编辑</AButton>
          <APopconfirm
            :content="row.isActive ? '确定禁用该用户？' : '确定启用该用户？'"
            @confirm="toggleUser(row)"
          >
            <AButton variant="text" size="small" :theme="row.isActive ? 'warning' : 'success'">
              {{ row.isActive ? '禁用' : '启用' }}
            </AButton>
          </APopconfirm>
          <APopconfirm
            content="删除后该账号将无法登录，确定删除？"
            @confirm="deleteUser(row)"
          >
            <AButton variant="text" size="small" theme="danger" :disabled="isSelf(row)">删除</AButton>
          </APopconfirm>
        </div>
      </template>
    </ATable>

    <!-- 添加/编辑弹窗 -->
    <AModal
      v-model:visible="modalVisible"
      :header="modalMode === 'create' ? '添加用户' : '编辑用户'"
      :confirm-btn="{ content: modalMode === 'create' ? '创建' : '保存', loading: modalLoading }"
      :close-on-overlay-click="false"
      width="560px"
      @confirm="handleSubmit"
    >
      <AForm ref="formRef" :model="formData" :rules="validationRules" layout="vertical" class="user-form">
        <AFormItem label="账号" field="username">
          <AInput v-model="formData.username" placeholder="登录账号" :disabled="modalMode === 'edit'" />
        </AFormItem>
        <AFormItem label="姓名" field="displayName">
          <AInput v-model="formData.displayName" placeholder="真实姓名" />
        </AFormItem>
        <AFormItem label="邮箱" field="email" class="user-form__span">
          <AInput v-model="formData.email" placeholder="用于密码找回" />
        </AFormItem>
        <AFormItem v-if="modalMode === 'create'" label="密码" field="password" class="user-form__span">
          <AInput v-model="formData.password" type="password" placeholder="请输入密码" />
        </AFormItem>
        <AFormItem label="角色" field="role" class="user-form__span">
          <ASelect v-model="formData.role" :options="roleOptions" placeholder="选择角色" />
        </AFormItem>
      </AForm>
    </AModal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { deleteAdminUser, getAdminUsers, updateAdminUser, signUpWithProfile } from '@/api/system'
import { useAuthStore } from '@/store/auth'
import { MessagePlugin } from '@/ui/message'
import type { AdminUser, AdminRole, CreateAdminUserDto, UpdateAdminUserDto } from '@/types'
import type { AppFormInstance, AppValidationRule } from '@/ui/arcoAppComponents'
import PageHeader from '@/components/PageHeader.vue'
import StatePanel from '@/components/StatePanel.vue'

const tableColumns = [
  { colKey: 'username', title: '账号', width: 130 },
  { colKey: 'displayName', title: '姓名', width: 110 },
  { colKey: 'email', title: '邮箱', ellipsis: true },
  { colKey: 'role', title: '角色', width: 90 },
  { colKey: 'isActive', title: '状态', width: 70 },
  { colKey: 'createdAt', title: '创建时间', width: 130 },
  { colKey: 'operation', title: '操作', width: 180, fixed: 'right' as const },
]
const authStore = useAuthStore()

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
const fetchError = ref('')
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
  fetchError.value = ''
  try { users.value = await getAdminUsers() }
  catch (err) {
    fetchError.value = err instanceof Error ? err.message : '获取用户列表失败'
    MessagePlugin.error(fetchError.value)
  }
  finally { loading.value = false }
}

function resetFilters() {
  searchKeyword.value = ''
  roleFilter.value = ''
}

function isSelf(user: AdminUser) {
  return authStore.user?.id === user.id
}

onMounted(fetchUsers)

const modalVisible = ref(false)
const modalMode = ref<'create' | 'edit'>('create')
const modalLoading = ref(false)
const editingUserId = ref<string | null>(null)
const formRef = ref<AppFormInstance | null>(null)

const formData = reactive<CreateAdminUserDto & { id?: string }>({
  username: '', displayName: '', email: '', password: '', role: 'viewer',
})

const validationRules: Record<string, AppValidationRule[]> = {
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

async function deleteUser(user: AdminUser) {
  if (isSelf(user)) {
    MessagePlugin.warning('不能删除当前登录账号')
    return
  }
  try {
    await deleteAdminUser(user.id)
    MessagePlugin.success('用户已删除')
    await fetchUsers()
  } catch (err) { MessagePlugin.error(err instanceof Error ? err.message : '删除失败') }
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

.admin-users :deep(.arco-table) {
  overflow: hidden;
  background: var(--bg-surface);
  border-radius: var(--radius-lg);
}

.table-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}

.user-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3) var(--space-4);
}

.user-form :deep(.arco-form-item) {
  margin-bottom: 0;
}

.user-form :deep(.arco-input-wrapper),
.user-form :deep(.arco-select-view-single) {
  width: 100%;
}

.user-form__span {
  grid-column: 1 / -1;
}

@media (max-width: 760px) {
  .user-toolbar,
  .table-actions {
    align-items: stretch;
    flex-direction: column;
  }
  .user-count { margin-left: 0; }
  .user-form { grid-template-columns: 1fr; }
}
</style>



