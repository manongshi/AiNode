function filenamePart(value) {
  return String(value || 'AI笔记')
    .replace(/[\\/:*?"<>|]/g, '_')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 72) || 'AI笔记'
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

export function exportMarkdown({ title, markdown }) {
  const content = markdown?.trim() || `# ${title || 'AI 笔记'}\n`
  downloadBlob(new Blob([content], { type: 'text/markdown;charset=utf-8' }), `${filenamePart(title)}.md`)
}
