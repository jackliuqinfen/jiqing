import type { App, Component, PropType } from 'vue'
import { defineComponent, h, ref } from 'vue'
import {
  Alert,
  Avatar,
  Badge,
  Button,
  Card,
  Checkbox,
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
  Table,
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
  IconEye,
  IconEyeInvisible,
  IconFile,
  IconFolder,
  IconImage,
  IconInfoCircle,
  IconList,
  IconLock,
  IconMenuFold,
  IconMenuUnfold,
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

export type AppValidationRule = Record<string, unknown>
export interface AppFormInstance {
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
  eye: IconEye,
  'eye-invisible': IconEyeInvisible,
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
  'menu-fold': IconMenuFold,
  'menu-unfold': IconMenuUnfold,
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

const AIcon = defineComponent({
  name: 'AIcon',
  props: { name: { type: String, required: true }, size: [String, Number] },
  setup(props, { attrs }) {
    return () => {
      const icon = iconMap[props.name] || IconApps
      const style = props.size ? { fontSize: typeof props.size === 'number' ? `${props.size}px` : props.size } : undefined
      return h(icon as any, { ...attrs, style: { ...((attrs.style as object) || {}), ...style } })
    }
  },
})

const AAppButton = defineComponent({
  name: 'AButton',
  inheritAttrs: false,
  setup(_, { attrs, slots }) {
    return () => h(Button as any, buttonProps(attrs), slots)
  },
})

const AAppInput = defineComponent({
  name: 'AInput',
  inheritAttrs: false,
  props: { clearable: Boolean },
  setup(props, { attrs, slots, expose }) {
    const attrsAny = attrs as Record<string, any>
    const inputRef = ref()
    expose({
      focus() {
        inputRef.value?.focus?.()
      },
      select() {
        const el = inputRef.value?.$el?.querySelector?.('input') as HTMLInputElement | null
        el?.select?.()
      },
    })
    return () => h(Input as any, { ...attrsAny, ref: inputRef, allowClear: props.clearable || Boolean(attrsAny.allowClear) }, {
      ...slots,
      prefix: slots['prefix-icon'] || slots.prefix,
      suffix: slots['suffix-icon'] || slots.suffix,
    })
  },
})

const AAppTextarea = defineComponent({
  name: 'ATextarea',
  inheritAttrs: false,
  setup(_, { attrs, slots }) {
    return () => h(Textarea as any, attrs, slots)
  },
})

const AAppSelect = defineComponent({
  name: 'ASelect',
  inheritAttrs: false,
  props: { clearable: Boolean },
  setup(props, { attrs, slots }) {
    const attrsAny = attrs as Record<string, any>
    return () => h(Select as any, { ...attrsAny, allowClear: props.clearable || Boolean(attrsAny.allowClear) }, slots)
  },
})

const AAppInputNumber = defineComponent({
  name: 'AInputNumber',
  inheritAttrs: false,
  setup(_, { attrs, slots }) {
    const mapped: Record<string, any> = { ...(attrs as Record<string, any>) }
    mapped.precision = mapped['decimal-places'] ?? mapped.precision
    delete mapped['decimal-places']
    return () => h(InputNumber as any, mapped, slots)
  },
})

const AAppDatePicker = defineComponent({
  name: 'ADatePicker',
  inheritAttrs: false,
  props: { clearable: Boolean },
  setup(props, { attrs, slots }) {
    const attrsAny = attrs as Record<string, any>
    return () => h(DatePicker as any, { ...attrsAny, allowClear: props.clearable || Boolean(attrsAny.allowClear) }, slots)
  },
})

const AAppForm = defineComponent({
  name: 'AForm',
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
        model: (attrs as Record<string, any>).model ?? props.data ?? {},
        rules: props.rules ?? (attrs as Record<string, any>).rules,
        layout: props.labelAlign === 'top' ? 'vertical' : ((attrs as Record<string, any>).layout || 'horizontal'),
      }
      if (props.labelWidth) {
        formProps.labelColProps = { style: { width: typeof props.labelWidth === 'number' ? `${props.labelWidth}px` : props.labelWidth } }
      }
      return h(Form as any, formProps, slots)
    }
  },
})

const AAppFormItem = defineComponent({
  name: 'AFormItem',
  inheritAttrs: false,
  setup(_, { attrs, slots }) {
    const mapped: Record<string, any> = { ...(attrs as Record<string, any>) }
    mapped.field = mapped.field ?? mapped.name
    mapped.extra = mapped.extra ?? mapped.help
    delete mapped.name
    delete mapped.help
    return () => h(FormItem as any, mapped, slots)
  },
})

const AAppModal = defineComponent({
  name: 'AModal',
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
      visible: (attrs as Record<string, any>).visible ?? props.visible,
      title: (attrs as Record<string, any>).title ?? props.header,
      okText: (attrs as Record<string, any>).okText ?? props.confirmBtn?.content,
      okLoading: Boolean((attrs as Record<string, any>).okLoading ?? props.confirmBtn?.loading),
      cancelText: (attrs as Record<string, any>).cancelText ?? props.cancelBtn?.content,
      hideOk: props.confirmBtn === null,
      unmountOnClose: Boolean((attrs as Record<string, any>)['destroy-on-close'] ?? (attrs as Record<string, any>).unmountOnClose),
      onBeforeOk: async () => {
        const beforeOk = (attrs as Record<string, any>).onBeforeOk
        if (typeof beforeOk === 'function') {
          return beforeOk()
        }
        emit('confirm')
        return false
      },
      'onUpdate:visible': (value: boolean) => emit('update:visible', value),
    }, slots)
  },
})

const AAppCard = defineComponent({
  name: 'ACard',
  inheritAttrs: false,
  setup(_, { attrs, slots }) {
    const mappedSlots = { ...slots }
    delete mappedSlots.actions
    return () => h(Card as any, attrs, { ...mappedSlots, extra: slots.actions || slots.extra })
  },
})

const AAppTag = defineComponent({
  name: 'ATag',
  inheritAttrs: false,
  setup(_, { attrs, slots }) {
    return () => h(Tag as any, tagProps(attrs), slots)
  },
})

const AAppTooltip = defineComponent({
  name: 'ATooltip',
  inheritAttrs: false,
  setup(_, { attrs, slots }) {
    return () => h(Tooltip as any, attrs, slots)
  },
})

const AAppAvatar = defineComponent({
  name: 'AAvatar',
  inheritAttrs: false,
  setup(_, { attrs, slots }) {
    return () => {
      const mapped: Record<string, any> = { ...(attrs as Record<string, any>) }
      mapped.size = numericSize(mapped.size, { small: 24, medium: 32, large: 40 })
      return h(Avatar as any, mapped, slots)
    }
  },
})

const AAppPopconfirm = defineComponent({
  name: 'APopconfirm',
  inheritAttrs: false,
  emits: ['confirm'],
  setup(_, { attrs, emit, slots }) {
    return () => h(Popconfirm as any, { ...attrs, onOk: () => emit('confirm') }, slots)
  },
})

const AAppAlert = defineComponent({
  name: 'AAlert',
  inheritAttrs: false,
  setup(_, { attrs, slots }) {
    const mapped: Record<string, any> = { ...(attrs as Record<string, any>) }
    mapped.type = mapped.theme || mapped.type
    delete mapped.theme
    delete mapped.close
    return () => h(Alert as any, mapped, slots)
  },
})

const AAppSpin = defineComponent({
  name: 'ASpin',
  inheritAttrs: false,
  props: { text: String },
  setup(props, { attrs }) {
    const mapped: Record<string, any> = { ...(attrs as Record<string, any>) }
    mapped.size = numericSize(mapped.size, { small: 16, medium: 24, large: 32 })
    return () => h(Spin as any, { ...mapped, tip: props.text })
  },
})

const AAppTable = defineComponent({
  name: 'ATable',
  inheritAttrs: false,
  props: {
    data: { type: Array as PropType<Record<string, unknown>[]>, default: () => [] },
    columns: { type: Array as PropType<Array<Record<string, any>>>, default: () => [] },
    loading: Boolean,
    bordered: Boolean,
    hover: Boolean,
  },
  setup(props, { attrs, slots }) {
    return () => {
      const columns = props.columns.map((column) => {
        const key = String(column.colKey || column.dataIndex || '')
        return {
          ...column,
          dataIndex: column.dataIndex || key,
          slotName: undefined,
          render: slots[key]
            ? ({ record }: { record: Record<string, unknown> }) => slots[key]?.({ row: record, record })
            : column.render,
        }
      })
      return h(Table as any, {
        ...attrs,
        data: props.data,
        columns,
        loading: props.loading,
        bordered: props.bordered,
        hoverable: props.hover,
      }, slots)
    }
  },
})

const components: Record<string, Component> = {
  AAlert: AAppAlert,
  AAvatar: AAppAvatar,
  ABadge: Badge,
  AButton: AAppButton,
  ACard: AAppCard,
  ACheckbox: Checkbox,
  ADatePicker: AAppDatePicker,
  AForm: AAppForm,
  AFormItem: AAppFormItem,
  AIcon,
  AInput: AAppInput,
  AInputNumber: AAppInputNumber,
  AModal: AAppModal,
  APopconfirm: AAppPopconfirm,
  ASelect: AAppSelect,
  ASpace: Space,
  ASpin: AAppSpin,
  ASwitch: Switch,
  ATable: AAppTable,
  ATag: AAppTag,
  ATextarea: AAppTextarea,
  ATooltip: AAppTooltip,
}

export function installArcoAppComponents(app: App) {
  Object.entries(components).forEach(([name, component]) => {
    app.component(name, component)
  })
}


