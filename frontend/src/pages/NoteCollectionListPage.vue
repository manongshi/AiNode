<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  activeTask: { type: Object, default: null },
  result: { type: Object, default: null },
  videoInfo: { type: Object, default: null },
  groups: { type: Array, default: () => [] },
  coverUrl: { type: Function, required: true },
  batchExportStatus: { type: Object, default: () => ({ groupId: '', state: '', text: '' }) },
})

const emit = defineEmits(['new-note', 'select-note', 'generate-video', 'export-group-pdfs'])
const query = ref('')
const expandedGroups = ref(new Set())
const taskIsRunning = computed(() => ['pending', 'running'].includes(props.activeTask?.status))
const filteredGroups = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  if (!keyword) return props.groups
  return props.groups.filter((group) => [group.title, group.bvid, ...(group.videos || []).map((video) => video.title)]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
    .includes(keyword))
})

function toggleGroup(groupId) {
  const next = new Set(expandedGroups.value)
  if (next.has(groupId)) next.delete(groupId)
  else next.add(groupId)
  expandedGroups.value = next
}

function generatedVideoCount(group) {
  return (group.videos || []).filter((video) => video.noteTaskId).length
}

</script>

<template>
  <aside class="note-group-panel">
    <header class="list-header"><h2>笔记</h2><span>⌘</span></header>
    <button class="new-note-button" @click="emit('new-note')">＋ 新建笔记</button>
    <label class="note-search"><span>⌕</span><input v-model="query" placeholder="搜索笔记或视频…" /></label>

    <div class="list-body">
      <section v-if="activeTask || result || videoInfo" class="current-note">
        <p class="list-section-title"><i></i>{{ taskIsRunning ? '进行中' : '当前笔记' }}</p>
        <article class="note-row selected">
          <div class="row-cover"><img v-if="(result?.video || videoInfo)?.cover" :src="coverUrl((result?.video || videoInfo).cover)" alt="视频封面" /><span v-else>AI</span></div>
          <div class="row-copy"><strong>{{ result?.video?.title || videoInfo?.title || '正在创建新笔记' }}</strong><span :class="taskIsRunning ? 'processing' : 'completed'">{{ taskIsRunning ? '正在处理' : '已完成' }}</span></div>
        </article>
      </section>

      <p v-if="filteredGroups.length" class="list-section-title"><i></i>最近笔记</p>
      <section v-for="group in filteredGroups" :key="group.groupId" class="note-group" :class="{ expanded: expandedGroups.has(group.groupId) }">
        <button class="group-summary" @click="toggleGroup(group.groupId)">
          <div class="row-cover"><img v-if="group.cover" :src="coverUrl(group.cover)" alt="视频封面" /><span v-else>AI</span></div>
          <div class="row-copy"><strong>{{ group.title }}</strong><span>{{ group.videoCount > 1 ? `合集 · ${group.videoCount} 个视频` : group.notes?.[0]?.createdAt }}</span></div>
          <b class="expand-icon">{{ expandedGroups.has(group.groupId) ? '⌃' : '⌄' }}</b>
        </button>

        <div v-if="expandedGroups.has(group.groupId)" class="group-details">
          <div class="group-detail-toolbar">
            <p class="group-detail-caption">已生成 {{ generatedVideoCount(group) }}/{{ group.videos.length }} 个视频</p>
            <button
              v-if="group.videoCount > 1"
              class="batch-export-action"
              :disabled="!generatedVideoCount(group) || (batchExportStatus.groupId === group.groupId && batchExportStatus.state === 'working')"
              @click="emit('export-group-pdfs', group)"
            >{{ batchExportStatus.groupId === group.groupId && batchExportStatus.state === 'working' ? '导出中…' : '导出到文件夹' }}</button>
          </div>
          <p v-if="batchExportStatus.groupId === group.groupId && batchExportStatus.text" class="batch-export-status" :class="batchExportStatus.state">{{ batchExportStatus.text }}</p>
          <article v-for="video in group.videos" :key="video.sourceUrl" class="collection-video-row">
            <div class="collection-video-copy"><span>P{{ video.page }}</span><strong>{{ video.title }}</strong></div>
            <button v-if="video.noteTaskId" class="open-note-action" @click="emit('select-note', video.noteTaskId)">查看</button>
            <button v-else class="generate-video-action" :disabled="taskIsRunning" @click="emit('generate-video', video.sourceUrl)">生成笔记</button>
          </article>
        </div>
      </section>

      <div v-if="!filteredGroups.length && !activeTask && !result && !videoInfo" class="list-empty"><span>▱</span><p>你的第一篇笔记<br />会出现在这里</p></div>
    </div>
  </aside>
</template>

<style scoped>
.note-group-panel { display: flex; flex-direction: column; min-height: 100vh; background: #fff; border-right: 1px solid #e7ebf3; }
.list-header { display: flex; align-items: center; justify-content: space-between; min-height: 68px; padding: 0 16px; border-bottom: 1px solid #edf0f5; }
.list-header h2 { margin: 0; color: #3c4657; font-size: 16px; }.list-header span { color: #8c96a6; font-size: 16px; }
.new-note-button { width: calc(100% - 32px); min-height: 44px; margin: 16px; color: #fff; background: #3e72ef; border: 0; border-radius: 8px; font-size: 14px; font-weight: 700; box-shadow: 0 5px 12px rgba(62, 114, 239, .2); }
.note-search { display: flex; gap: 7px; align-items: center; margin: 0 16px 16px; padding: 0 11px; color: #a5adba; background: #f7f8fa; border: 1px solid #eaedf2; border-radius: 7px; }.note-search input { width: 100%; height: 35px; color: #374151; background: transparent; border: 0; outline: 0; font-size: 12px; }.note-search input::placeholder { color: #b4bbc6; }
.list-body { flex: 1; overflow-y: auto; border-top: 1px solid #edf0f5; }.list-section-title { display: flex; gap: 6px; align-items: center; margin: 12px 16px 7px; color: #4a77ef; font-size: 12px; font-weight: 700; }.list-section-title i { width: 7px; height: 7px; background: #70a3ff; border-radius: 50%; }
.note-row, .group-summary { display: flex; width: 100%; gap: 10px; padding: 12px 16px; border: 0; border-left: 3px solid transparent; background: #fff; cursor: pointer; text-align: left; }.note-row.selected { background: #eff4ff; border-left-color: #3c73f4; }.group-summary:hover { background: #f6f8fc; }
.row-cover { display: grid; flex: 0 0 auto; width: 50px; height: 40px; overflow: hidden; place-items: center; color: #4f79eb; background: #e1eaff; border-radius: 4px; font-size: 10px; font-weight: 800; }.row-cover img { width: 100%; height: 100%; object-fit: cover; }
.row-copy { min-width: 0; flex: 1; }.row-copy strong { display: -webkit-box; overflow: hidden; color: #3b4657; font-size: 12px; line-height: 1.4; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }.row-copy span { display: block; margin-top: 4px; color: #a0a9b5; font-size: 10px; }.row-copy .processing { color: #ec951c; }.row-copy .completed { color: #2a9a68; }
.expand-icon { align-self: center; color: #7990b6; font-size: 13px; }.note-group.expanded { background: #fbfcff; border-bottom: 1px solid #edf1f7; }.note-group.expanded .group-summary { background: #f4f7ff; }
.group-details { padding: 4px 13px 12px 16px; }.group-detail-toolbar { display: flex; gap: 8px; align-items: center; justify-content: space-between; margin: 7px 0 5px 60px; }.group-detail-caption { margin: 0; color: #7e91ad; font-size: 10px; font-weight: 700; }.batch-export-action { flex: 0 0 auto; padding: 5px 7px; color: #315fc4; background: #edf3ff; border: 1px solid #cfddfb; border-radius: 5px; font-size: 9px; font-weight: 800; }.batch-export-action:hover:not(:disabled) { color: #fff; background: #3e72ef; border-color: #3e72ef; }.batch-export-action:disabled { cursor: wait; opacity: .55; }.batch-export-status { margin: 6px 0 7px 13px; padding: 6px 8px; color: #597298; background: #f1f5fc; border-radius: 5px; font-size: 9px; line-height: 1.45; }.batch-export-status.success { color: #28795d; background: #edf8f3; }.batch-export-status.error { color: #a45249; background: #fff1ef; }.collection-video-row { display: flex; gap: 8px; align-items: center; padding: 8px 0 8px 13px; border-left: 2px solid #dce7ff; }.collection-video-copy { display: flex; min-width: 0; flex: 1; gap: 6px; align-items: baseline; }.collection-video-copy span { flex: 0 0 auto; color: #4c7bee; font-size: 10px; font-weight: 800; }.collection-video-copy strong { overflow: hidden; color: #59677b; font-size: 11px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }.generate-video-action, .open-note-action { flex: 0 0 auto; padding: 4px 7px; border-radius: 5px; font-size: 10px; font-weight: 700; }.generate-video-action { color: #326fe8; background: #edf3ff; border: 1px solid #d5e2ff; }.generate-video-action:disabled { cursor: wait; opacity: .6; }.open-note-action { color: #278d68; background: #eff9f4; border: 1px solid #d0eadc; }
.list-empty { display: grid; place-items: center; min-height: 340px; color: #c5cad2; text-align: center; }.list-empty span { font-size: 42px; opacity: .45; }.list-empty p { margin: 9px 0 0; font-size: 12px; line-height: 1.8; }
@media (max-width: 1180px) { .note-group-panel { display: none; } }
</style>
