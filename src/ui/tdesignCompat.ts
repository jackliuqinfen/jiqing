import type { App, Component, PropType } from 'vue'
import { defineComponent, h, ref } from 'vue'
import {
  Alert,
  Avatar,
  Badge,
  Button,
  Card,
  DatePicker,
  Form,
  FormItem,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Spin,
  Switch,
  Tag,
  Textarea,
  Tooltip,
} from '@arco-design/web-vue'
import {
  IconApps,
  IconCheck,
  IconCheckCircle,
  IconCheckSquare,
  IconClose,
  IconCopy,
  IconDashboard,
  IconEdit,
  IconExclamationCircle,
  IconFile,
  IconFolder,
  IconImage,
  IconInfoCircle,
  IconList,
  IconLock,
  IconPhone,
  IconPlayCircle,
  IconPlus,
  IconRefresh,
  IconSearch,
  IconSettings,
  IconTag,
  IconUndo,
  IconUpload,
  IconUser,
  IconUserAdd,
  IconUserGroup,
} from '@arco-design/web-vue/es/icon'

export type FormRule = Record<string, unknown>
export interface FormInstanceFunctions {
  validate: () => Promise<boolean>
  clearValidate?: () => void
  resetFields?: () => void
}

const iconMap: Record<string, Component> = {
  add: IconPlus,
  call: IconPhone,
  check: IconCheck,
  'check-circle': IconCheckCircle,
  close: IconClose,
  dashboard: IconDashboard,
  edit: IconEdit,
  'edit-1': IconEdit,
  'error-circle': IconExclamationCircle,
  flag: IconTag,
  'file-copy': IconCopy,
  'file-paste': IconFile,
  folder: IconFolder,
  image: IconImage,
  inbox: IconFile,
  'info-circle': IconInfoCircle,
  layers: IconApps,
  list: IconList,
  'lock-on': IconLock,
  'play-circle': IconPlayCircle,
  refresh: IconRefresh,
  rollback: IconUndo,
  search: IconSearch,
  setting: IconSettings,
  'system-setting': IconSettings,
  task: IconCheckSquare,
  upload: IconUpload,
  user: IconUser,
  'user-add': IconUserAdd,
  'user-checked': IconUser,
  usergroup: IconUserGroup,
  'view-module': IconApps,
}

function numericSize(size: unknown, sizes: Record<string, number>) {
  if (typeof size === 'number') return size
  if (typeof size === 'string') return sizes[size] ?? (Number(size) || undefined)
  return undefined
}

function buttonProps(props: Record<string, unknown>) {
  const theme = props.theme as string | undefined
  const variant = props.variant as string | undefined
  const mapped: Record<string, unknown> = { ...props }
  const nativeType = mapped.type
  delete mapped.theme
  delete mapped.variant
  if (nativeType === 'submit' || nativeType === 'reset' || nativeType === 'button') {
    mapped.htmlType = nativeType
    delete mapped.type
  }
  if (variant === 'text') mapped.type = 'text'
  else if (variant === 'outline') mapped.type = 'outline'
  else if (theme === 'primary') mapped.type = 'primary'
  else mapped.type = mapped.type || 'secondary'
  if (theme && ['success', 'warning', 'danger'].includes(theme)) mapped.status = theme
  return mapped
}

function tagProps(props: Record<string, unknown>) {
  const theme = props.theme as string | undefined
  const mapped: Record<string, unknown> = { ...props }
  delete mapped.theme
  delete mapped.variant
  if (theme === 'danger') mapped.color = 'red'
  else if (theme === 'warning') mapped.color = 'orange'
  else if (theme === 'success') mapped.color = 'green'
  else if (theme === 'primary') mapped.color = 'arcoblue'
  else if (theme && theme !== 'default') mapped.color = theme
  return mapped
}

const TIcon = defineComponent({
  name: 'TIcon',
  props: { name: { type: String, required: true }, size: [String, Number] },
  setup(props, { attrs }) {
    return () => {
      const icon = iconMap[props.name] || IconApps
      const style = props.size ? { fontSize: typeof props.size === 'number' ? `${props.size}px` : props.size } : undefined
      return h(icon as any, { ...attrs, style: { ...(attrs.style as object || {}), ...style } })
    }
  },
})

const TButton = defineComponent({
  name: 'TButton',
  inheritAttrs: false,
  setup(_, { attrs, slots }) {
    return () => h(Button as any, buttonProps(attrs), slots)
  },
})

const TInput = defineComponent({
  name: 'TInput',
  inheritAttrs: false,
  props: { clearable: Boolean },
  setup(props, { attrs, slots }) {
    const attrsAny = attrs as Record<string, any>
    return () => h(Input as any, { ...attrsAny, allowClear: props.clearable || Boolean(attrsAny.allowClear) }, {
      ...slots,
      prefix: slots['prefix-icon'] || slots.prefix,
    })
  },
})

const TTextarea = defineComponent({
  name: 'TTextarea',
  inheritAttrs: false,
  setup(_, { attrs, slots }) {
    return () => h(Textarea as any, attrs, slots)
  },
})

const TSelect = defineComponent({
  name: 'TSelect',
  inheritAttrs: false,
  props: { clearable: Boolean },
  setup(props, { attrs, slots }) {
    const attrsAny = attrs as Record<string, any>
    return () => h(Select as any, { ...attrsAny, allowClear: props.clearable || Boolean(attrsAny.allowClear) }, slots)
  },
})

const TInputNumber = defineComponent({
  name: 'TInputNumber',
  inheritAttrs: false,
  setup(_, { attrs, slots }) {
    const mapped: Record<string, any> = { ...(attrs as Record<string, any>) }
    mapped.precision = mapped['decimal-places'] ?? mapped.precision
    delete mapped['decimal-places']
    return () => h(InputNumber as any, mapped, slots)
  },
})

const TDatePicker = defineComponent({
  name: 'TDatePicker',
  inheritAttrs: false,
  props: { clearable: Boolean },
  setup(props, { attrs, slots }) {
    const attrsAny = attrs as Record<string, any>
    return () => h(DatePicker as any, { ...attrsAny, allowClear: props.clearable || Boolean(attrsAny.allowClear) }, slots)
  },
})

const TForm = defineComponent({
  name: 'TForm',
  inheritAttrs: false,
  props: {
    data: Object,
    rules: Object,
    labelAlign: String,
    labelWidth: [String, Number],
  },
  setup(props, { attrs, slots, expose }) {
    const formRef = ref()
    expose({
      async validate() {
        const errors = await formRef.value?.validate?.()
        return !errors
      },
      clearValidate() {
        formRef.value?.clearValidate?.()
      },
      resetFields() {
        formRef.value?.resetFields?.()
      },
    })
    return () => {
      const formProps: Record<string, any> = {
        ...attrs,
        ref: formRef,
        model: props.data ?? {},
        rules: props.rules,
        layout: props.labelAlign === 'top' ? 'vertical' : 'horizontal',
      }
      if (props.labelWidth) {
        formProps.labelColProps = { style: { width: typeof props.labelWidth === 'number' ? `${props.labelWidth}px` : props.labelWidth } }
      }
      return h(Form as any, formProps, slots)
    }
  },
})

const TFormItem = defineComponent({
  name: 'TFormItem',
  inheritAttrs: false,
  setup(_, { attrs, slots }) {
    const mapped: Record<string, any> = { ...(attrs as Record<string, any>) }
    mapped.field = mapped.name
    mapped.extra = mapped.help
    delete mapped.name
    delete mapped.help
    return () => h(FormItem as any, mapped, slots)
  },
})

const TDialog = defineComponent({
  name: 'TDialog',
  inheritAttrs: false,
  props: {
    visible: Boolean,
    header: String,
    confirmBtn: [Object, null] as PropType<Record<string, unknown> | null>,
    cancelBtn: Object as PropType<Record<string, unknown>>,
  },
  emits: ['update:visible', 'confirm'],
  setup(props, { attrs, emit, slots }) {
    return () => h(Modal as any, {
      ...attrs,
      visible: props.visible,
      title: props.header,
      okText: props.confirmBtn?.content as string | undefined,
      okLoading: Boolean(props.confirmBtn?.loading),
      cancelText: props.cancelBtn?.content as string | undefined,
      hideOk: props.confirmBtn === null,
      unmountOnClose: Boolean(attrs['destroy-on-close']),
      onBeforeOk: () => {
        emit('confirm')
        return false
      },
      'onUpdate:visible': (value: boolean) => emit('update:visible', value),
    }, slots)
  },
})

const TCard = defineComponent({
  name: 'TCard',
  inheritAttrs: false,
  setup(_, { attrs, slots }) {
    return () => {
      const mappedSlots = { ...slots }
      delete mappedSlots.actions
      return h(Card as any, attrs, { ...mappedSlots, extra: slots.actions || slots.extra })
    }
  },
})

const TTag = defineComponent({
  name: 'TTag',
  inheritAttrs: false,
  setup(_, { attrs, slots }) {
    return () => h(Tag as any, tagProps(attrs), slots)
  },
})

const TTooltip = defineComponent({
  name: 'TTooltip',
  inheritAttrs: false,
  setup(_, { attrs, slots }) {
    return () => h(Tooltip as any, attrs, slots)
  },
})

const TAvatar = defineComponent({
  name: 'TAvatar',
  inheritAttrs: false,
  setup(_, { attrs, slots }) {
    return () => {
      const mapped: Record<string, any> = { ...(attrs as Record<string, any>) }
      mapped.size = numericSize(mapped.size, { small: 24, medium: 32, large: 40 })
      return h(Avatar as any, mapped, slots)
    }
  },
})

const TSpace = defineComponent({
  name: 'TSpace',
  inheritAttrs: false,
  setup(_, { attrs, slots }) {
    return () => h(Space as any, attrs, slots)
  },
})

const TPopconfirm = defineComponent({
  name: 'TPopconfirm',
  inheritAttrs: false,
  emits: ['confirm'],
  setup(_, { attrs, emit, slots }) {
    return () => h(Popconfirm as any, { ...attrs, onOk: () => emit('confirm') }, slots)
  },
})

const TSwitch = defineComponent({
  name: 'TSwitch',
  inheritAttrs: false,
  setup(_, { attrs, slots }) {
    return () => h(Switch as any, attrs, slots)
  },
})

const TBadge = defineComponent({
  name: 'TBadge',
  inheritAttrs: false,
  setup(_, { attrs, slots }) {
    return () => h(Badge as any, attrs, slots)
  },
})

const TAlert = defineComponent({
  name: 'TAlert',
  inheritAttrs: false,
  setup(_, { attrs, slots }) {
    const mapped: Record<string, any> = { ...(attrs as Record<string, any>) }
    mapped.type = mapped.theme || mapped.type
    delete mapped.theme
    delete mapped.close
    return () => h(Alert as any, mapped, slots)
  },
})

const TLoading = defineComponent({
  name: 'TLoading',
  inheritAttrs: false,
  props: { text: String },
  setup(props, { attrs }) {
    return () => {
      const mapped: Record<string, any> = { ...(attrs as Record<string, any>) }
      mapped.size = numericSize(mapped.size, { small: 16, medium: 24, large: 32 })
      return h(Spin as any, { ...mapped, tip: props.text })
    }
  },
})

const TTable = defineComponent({
  name: 'TTable',
  inheritAttrs: false,
  props: {
    data: { type: Array as PropType<Record<string, unknown>[]>, default: () => [] },
    columns: { type: Array as PropType<Array<Record<string, unknown>>>, default: () => [] },
    loading: Boolean,
    bordered: Boolean,
    hover: Boolean,
  },
  setup(props, { slots }) {
    return () => {
      if (props.loading) return h('div', { class: 'compat-table-loading' }, '加载中...')
      return h('table', {
        class: ['compat-table', props.bordered && 'compat-table--bordered', props.hover && 'compat-table--hover'],
      }, [
        h('thead', [
          h('tr', props.columns.map((col) => h('th', { style: col.width ? { width: `${col.width}px` } : undefined }, String(col.title || '')))),
        ]),
        h('tbody', props.data.length
          ? props.data.map((row) => h('tr', { key: String(row.id || row.key || JSON.stringify(row)) }, props.columns.map((col) => {
            const key = String(col.colKey || col.dataIndex || '')
            const slot = slots[key]
            return h('td', slot ? slot({ row }) : String(row[key] ?? ''))
          })))
          : [h('tr', [h('td', { colspan: props.columns.length || 1 }, h('div', { class: 'compat-table-empty' }, '暂无数据'))])]),
      ])
    }
  },
})

const components: Record<string, Component> = {
  TAlert,
  TAvatar,
  TBadge,
  TButton,
  TCard,
  TDatePicker,
  TDialog,
  TForm,
  TFormItem,
  TIcon,
  TInput,
  TInputNumber,
  TLoading,
  TPopconfirm,
  TSelect,
  TSpace,
  TSwitch,
  TTable,
  TTag,
  TTextarea,
  TTooltip,
}

export function installTDesignCompat(app: App) {
  Object.entries(components).forEach(([name, component]) => {
    app.component(name, component)
  })
}
