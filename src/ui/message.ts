import { Message } from '@arco-design/web-vue'

type MessageContent = string | { content?: string }

function text(content: MessageContent): string {
  return typeof content === 'string' ? content : content.content || ''
}

export const MessagePlugin = {
  success(content: MessageContent) {
    Message.success(text(content))
  },
  warning(content: MessageContent) {
    Message.warning(text(content))
  },
  error(content: MessageContent) {
    Message.error(text(content))
  },
  info(content: MessageContent) {
    Message.info(text(content))
  },
}

