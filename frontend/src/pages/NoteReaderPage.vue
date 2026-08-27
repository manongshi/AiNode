<script setup>
import { computed, ref } from 'vue'

import NoteDocument from '../components/NoteDocument.vue'
import NoteOutline from '../components/NoteOutline.vue'
import MindMapView from '../components/MindMapView.vue'
import { createMarkmapData } from '../utils/markmapData'
import { exportMarkdown } from '../utils/noteExport'
import { createNoteDocument } from '../utils/markdownNote'

const props = defineProps({
  result: {
    type: Object,
    required: true,
  },
  styleLabel: {
    type: String,
    default: '结构化笔记',
  },
  noteTaskId: {
    type: String,
    default: '',
  },
  coverUrl: {
    type: Function,
    required: true,
  },
})

const activeView = ref('note')
const noteDocument = computed(() => createNoteDocument(props.result.note))
const markmapData = computed(() => createMarkmapData(props.result.mindMap))
const originalVideoUrl = computed(() => {
  if (props.result?.video?.sourceUrl) return props.result.video.sourceUrl
  const bvid = props.result?.video?.bvid
  if (!bvid) return ''
  const page = Number(props.result.video.page) || 1
  return `https://www.bilibili.com/video/${encodeURIComponent(bvid)}${page > 1 ? `?p=${page}` : ''}`
})
const sourceLabel = computed(() => props.result?.video?.platform === 'douyin' ? '查看抖音原视频 ↗' : '查看 B 站原视频 ↗')
const displayedType = computed(() => props.result?.contentType || props.styleLabel)
const collection = computed(() => props.result?.collection || null)
const activeHeading = ref('')
const readerMain = ref(null)
const exportingPdf = ref(false)
const pdfExportError = ref('')

function selectHeading(id) {
  activeHeading.value = id
  const container = readerMain.value
  const target = container?.querySelector(`[id="${id}"]`)
  if (!container || !target) return
  const offset = target.getBoundingClientRect().top - container.getBoundingClientRect().top
  container.scrollBy({ top: offset - 24, behavior: 'smooth' })
}

function formatTime(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0))
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}

function formatDuration(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0))
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const remaining = total % 60
  return hours ? `${hours}:${String(minutes).padStart(2, '0')}:${String(remaining).padStart(2, '0')}` : `${String(minutes).padStart(2, '0')}:${String(remaining).padStart(2, '0')}`
}

function exportNoteMarkdown() {
  exportMarkdown({ title: props.result.video.title, markdown: props.result.note })
}

async function exportNotePdf() {
  if (exportingPdf.value || !props.noteTaskId) return
  exportingPdf.value = true
  pdfExportError.value = ''
  try {
    const response = await fetch(`/api/v1/notes/${encodeURIComponent(props.noteTaskId)}/export/pdf`)
    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      throw new Error(data.detail || 'PDF 导出失败，请稍后重试。')
    }
    const blob = await response.blob()
    const fileUrl = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = fileUrl
    anchor.download = `${props.result.video.title || 'AI笔记'}.pdf`
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    window.setTimeout(() => URL.revokeObjectURL(fileUrl), 1000)
  } catch (error) {
    pdfExportError.value = error.message || 'PDF 导出失败，请稍后重试。'
  } finally {
    exportingPdf.value = false
  }
}
</script>

<template>
  <section class="reader-page">
    <header class="reader-header">
      <div class="reader-source">
        <div class="reader-cover">
          <img v-if="result.video.cover" :src="coverUrl(result.video.cover)" alt="视频封面" />
          <span v-else>VIDEO</span>
        </div>
        <div class="reader-title">
          <p>视频笔记 / {{ displayedType }}</p>
          <h2>{{ result.video.title }}</h2>
          <div class="reader-source-meta">
            <span>{{ result.video.bvid }} · 第 {{ result.video.page }} P · {{ result.subtitle.lines.length }} 条字幕</span>
            <a v-if="originalVideoUrl" :href="originalVideoUrl" target="_blank" rel="noopener noreferrer">{{ sourceLabel }}</a>
          </div>
        </div>
      </div>
      <div class="reader-actions">
        <button class="export-button" @click="exportNoteMarkdown">导出 Markdown</button>
        <button class="export-button primary" :disabled="exportingPdf || !noteTaskId" @click="exportNotePdf">{{ exportingPdf ? '正在生成 PDF…' : '导出 PDF' }}</button>
        <div class="reader-meta">
          <strong>{{ result.chunk_count }}</strong>
          <span>段内容</span>
        </div>
      </div>
    </header>
    <p v-if="pdfExportError" class="pdf-export-error">{{ pdfExportError }}</p>

    <details v-if="collection" class="reader-collection">
      <summary>
        <span>合集明细</span>
        <strong>{{ collection.videoCount }} 集 · 总时长 {{ formatDuration(collection.totalDuration) }}</strong>
      </summary>
      <div class="reader-collection-list">
        <a v-for="video in collection.videos" :key="video.sourceUrl" :href="video.sourceUrl" target="_blank" rel="noopener noreferrer">
          <span>P{{ video.page }}</span>
          <b>{{ video.title }}</b>
          <time>{{ formatDuration(video.duration) }}</time>
        </a>
      </div>
    </details>

    <div class="reader-tabs" role="tablist" aria-label="笔记内容切换">
      <button :class="{ active: activeView === 'note' }" @click="activeView = 'note'">文档阅读</button>
      <button :class="{ active: activeView === 'subtitle' }" @click="activeView = 'subtitle'">原始字幕</button>
      <button :class="{ active: activeView === 'mind-map' }" @click="activeView = 'mind-map'">思维导图</button>
    </div>

    <div v-if="activeView === 'note'" class="reader-layout">
      <NoteOutline :items="noteDocument.outline" :active-id="activeHeading" @select="selectHeading" />
      <main ref="readerMain" class="reader-main">
        <NoteDocument :html="noteDocument.html" />
      </main>
    </div>

    <div v-else-if="activeView === 'subtitle'" class="reader-subtitles">
      <div v-for="(line, index) in result.subtitle.lines" :key="`${line.start}-${index}`" class="reader-subtitle-line">
        <time>{{ formatTime(line.start) }}</time>
        <p>{{ line.content }}</p>
      </div>
    </div>
    <MindMapView v-else :mind-map="markmapData" />
  </section>
</template>

<style scoped>
.reader-page { display: flex; flex-direction: column; height: 100%; min-height: 0; padding: 30px 34px 0; overflow: hidden; }
.reader-header { display: flex; justify-content: space-between; gap: 20px; padding-bottom: 24px; border-bottom: 1px solid #dce9e2; }
.reader-source { display: flex; min-width: 0; gap: 17px; align-items: center; }
.reader-cover { display: grid; flex: 0 0 auto; width: 106px; height: 67px; overflow: hidden; place-items: center; color: #38715d; background: #eaf5ef; font-size: 10px; font-weight: 800; }
.reader-cover img { width: 100%; height: 100%; object-fit: cover; }
.reader-title { min-width: 0; }
.reader-title p { margin: 0 0 6px; color: #278f6c; font-size: 10px; font-weight: 800; letter-spacing: .13em; text-transform: uppercase; }
.reader-title h2 { margin: 0; overflow: hidden; color: #1d4033; font-size: clamp(18px, 2.2vw, 27px); letter-spacing: -.06em; line-height: 1.2; text-overflow: ellipsis; white-space: nowrap; }
.reader-source-meta { display: flex; flex-wrap: wrap; gap: 8px 13px; align-items: center; margin-top: 6px; }
.reader-source-meta span { color: #92a89d; font-size: 10px; }
.reader-source-meta a { color: #327fdd; font-size: 10px; font-weight: 700; text-decoration: none; }
.reader-source-meta a:hover { text-decoration: underline; }
.reader-meta { display: grid; flex: 0 0 auto; align-content: center; text-align: right; }
.reader-meta strong { color: #258d68; font-size: 31px; line-height: 1; }
.reader-meta span { margin-top: 4px; color: #91a59b; font-size: 10px; }
.reader-actions { display: flex; flex: 0 0 auto; gap: 8px; align-items: center; }
.reader-collection { margin-top: 12px; padding: 0 13px; color: #4f6f63; background: #f5faf7; border: 1px solid #dcece3; border-radius: 8px; }
.reader-collection summary { display: flex; justify-content: space-between; gap: 14px; align-items: center; min-height: 35px; cursor: pointer; list-style: none; }
.reader-collection summary::-webkit-details-marker { display: none; }
.reader-collection summary span { color: #287f5d; font-size: 11px; font-weight: 800; }
.reader-collection summary strong { color: #78978a; font-size: 10px; font-weight: 700; }
.reader-collection-list { max-height: 180px; padding: 0 0 8px; overflow-y: auto; }
.reader-collection-list a { display: grid; grid-template-columns: 37px minmax(0, 1fr) 52px; gap: 9px; padding: 8px 2px; color: #5e7a6e; border-top: 1px solid #e4f0e9; font-size: 11px; text-decoration: none; }
.reader-collection-list a:hover b { color: #247e5b; text-decoration: underline; }
.reader-collection-list span { color: #2a966d; font-weight: 800; }
.reader-collection-list b { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.reader-collection-list time { color: #90a89d; text-align: right; }
.export-button { min-height: 31px; padding: 0 10px; color: #527569; background: #fff; border: 1px solid #d6e7df; border-radius: 6px; font-size: 11px; font-weight: 700; white-space: nowrap; }
.export-button:hover { color: #1f815f; background: #f2faf6; border-color: #a7d7c2; }
.export-button.primary { color: #fff; background: #2c966f; border-color: #2c966f; }
.export-button.primary:hover { background: #227c5b; }
.export-button:disabled { cursor: wait; opacity: .7; }
.pdf-export-error { margin: 8px 0 0; color: #c55b52; font-size: 11px; }
.reader-tabs { display: flex; gap: 28px; border-bottom: 1px solid #dce9e2; }
.reader-tabs button { position: relative; padding: 18px 0 13px; color: #8ba097; background: transparent; border: 0; font-size: 12px; font-weight: 700; cursor: pointer; }
.reader-tabs button.active { color: #1d805d; }
.reader-tabs button.active::after { position: absolute; right: 0; bottom: -1px; left: 0; height: 2px; background: #2c966f; content: ''; }
.reader-layout { display: grid; grid-template-columns: minmax(155px, 20%) minmax(0, 1fr); flex: 1; min-height: 0; gap: 34px; padding-top: 29px; overflow: hidden; background: #f6faf7; }
.reader-main { min-width: 0; min-height: 0; padding-right: 8px; overflow-y: auto; }
.reader-subtitles { flex: 1; min-height: 0; overflow-y: auto; padding: 12px 8px 30px 0; }
.reader-subtitle-line { display: grid; grid-template-columns: 58px 1fr; gap: 16px; padding: 13px 0; border-bottom: 1px solid #edf3ee; }
.reader-subtitle-line time { padding-top: 3px; color: #258d68; font-size: 10px; font-weight: 800; }
.reader-subtitle-line p { margin: 0; color: #567167; font-size: 13px; line-height: 1.75; }

@media (max-width: 880px) {
  .reader-page { padding: 23px 23px 0; }
  .reader-layout { grid-template-columns: 1fr; gap: 20px; overflow-y: auto; }
}

@media (max-width: 600px) {
  .reader-page { padding: 18px 18px 0; }
  .reader-header { align-items: flex-start; }
  .reader-cover { width: 74px; height: 52px; }
  .reader-title h2 { font-size: 17px; }
  .reader-meta { display: none; }
  .reader-actions { gap: 5px; }
  .export-button { padding: 0 7px; font-size: 10px; }
}
</style>
