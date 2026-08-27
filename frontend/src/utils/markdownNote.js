import DOMPurify from 'dompurify'
import { marked } from 'marked'

function headingId(index) {
  return `note-heading-${index + 1}`
}

export function createNoteDocument(markdown) {
  const rawHtml = marked.parse(markdown || '', {
    breaks: false,
    gfm: true,
  })
  const container = document.createElement('div')
  container.innerHTML = rawHtml

  const outline = Array.from(container.querySelectorAll('h1, h2, h3, h4')).map((heading, index) => {
    const id = headingId(index)
    heading.id = id
    return {
      id,
      level: Number(heading.tagName.slice(1)),
      title: heading.textContent.trim(),
    }
  })

  return {
    outline,
    html: DOMPurify.sanitize(container.innerHTML, { ADD_ATTR: ['id'] }),
  }
}
