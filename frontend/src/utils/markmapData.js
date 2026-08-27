import { markRaw } from 'vue'

const MAX_NODES = 260
const MAX_DEPTH = 8
const MAX_CONTENT_LENGTH = 96

function normalizeContent(value) {
  return String(value ?? '')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, MAX_CONTENT_LENGTH)
}

/**
 * 将 AI 返回的树转成供 Markmap 消费的普通对象。
 * Markmap 会在节点上写入运行时状态；必须与 Vue 的响应式对象隔离，
 * 否则深度监听会在每次绘制后再次触发，导致页面不断重绘。
 */
export function createMarkmapData(source) {
  let nodeCount = 0

  function visit(node, depth) {
    if (!node || typeof node !== 'object' || depth > MAX_DEPTH || nodeCount >= MAX_NODES) return null

    const content = normalizeContent(node.content)
    if (!content) return null

    nodeCount += 1
    const children = Array.isArray(node.children)
      ? node.children.map((child) => visit(child, depth + 1)).filter(Boolean)
      : []

    return { content, children }
  }

  const tree = visit(source, 0)
  return tree ? markRaw(tree) : null
}
