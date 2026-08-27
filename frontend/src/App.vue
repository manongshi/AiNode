<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import AppSidebar from './components/AppSidebar.vue'
import TaskTimeline from './components/TaskTimeline.vue'
import AuthPage from './pages/AuthPage.vue'
import NoteCollectionListPage from './pages/NoteCollectionListPage.vue'
import NoteReaderPage from './pages/NoteReaderPage.vue'
import VideoNoteComposer from './pages/VideoNoteComposer.vue'

const url = ref('')
const style = ref('structured')
const extraInstruction = ref('')
const modelProvider = ref('deepseek')
const loading = ref(false)
const infoLoading = ref(false)
const error = ref('')
const result = ref(null)
const videoInfo = ref(null)
const activeTask = ref(null)
const savedNoteGroups = ref([])
const loadedVideoInput = ref('')
const selectedVideoUrls = ref([])
const currentNoteTaskId = ref('')
const sidebarCollapsed = ref(false)
const noteListCollapsed = ref(false)
const authLoading = ref(true)
const currentUser = ref(null)
const batchExportStatus = ref({ groupId: '', state: '', text: '' })
let taskEvents = null

const taskStorageKey = () => `ainote.activeTaskId.${currentUser.value?.id || 'guest'}`

const styleOptions = [
  { value: 'structured', label: '结构化笔记', hint: '把内容整理成清晰章节' },
  { value: 'study', label: '学习复习', hint: '突出概念、例子与问题' },
  { value: 'brief', label: '极简摘要', hint: '只留下结论和行动建议' },
]

const selectedStyleLabel = computed(() => styleOptions.find((item) => item.value === style.value)?.label || '结构化笔记')

const taskIsRunning = computed(() => ['pending', 'running'].includes(activeTask.value?.status))
const estimatedPointsCost = computed(() => {
  if (!videoInfo.value) return 0
  const selectedUrls = new Set(selectedVideoUrls.value)
  const durations = videoInfo.value?.is_multipart
    ? (videoInfo.value.videos || []).filter((item) => selectedUrls.has(item.url)).map((item) => Number(item.duration_seconds || 0))
    : [Number(videoInfo.value.duration_seconds || 0)]
  const totalSeconds = durations.reduce((sum, duration) => sum + duration, 0)
  return totalSeconds > 0 ? Math.max(1, Math.ceil(totalSeconds / 60)) : Math.max(1, durations.length)
})

async function loadCurrentUser() {
  try {
    const response = await fetch('/api/auth/me')
    if (!response.ok) return false
    currentUser.value = await response.json()
    return true
  } finally {
    authLoading.value = false
  }
}

async function handleAuthenticated(user) {
  currentUser.value = user
  authLoading.value = false
  await loadSavedNotes()
  const taskId = window.localStorage.getItem(taskStorageKey())
  if (taskId) restoreTask(taskId)
}

async function logout() {
  closeTaskEvents()
  await fetch('/api/auth/logout', { method: 'POST' })
  resetAll()
  currentUser.value = null
  savedNoteGroups.value = []
}

async function loadVideoInfo() {
  error.value = ''
  if (!url.value.trim()) {
    error.value = '请先粘贴一个视频链接。'
    return false
  }

  infoLoading.value = true
  result.value = null
  try {
    const response = await fetch('/api/bilibili/video/fetch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: url.value.trim() }),
    })
    const data = await response.json()
    if (!response.ok) throw new Error(data.detail || '读取视频信息失败，请稍后重试。')
    videoInfo.value = data.data
    loadedVideoInput.value = url.value.trim()
    selectedVideoUrls.value = data.data?.is_multipart
      ? (data.data.videos || []).map((item) => item.url).filter(Boolean)
      : []
    return true
  } catch (requestError) {
    videoInfo.value = null
    error.value = requestError.message || '网络请求失败，请确认后端已经启动。'
    return false
  } finally {
    infoLoading.value = false
  }
}

async function generateNote() {
  error.value = ''

  if (!url.value.trim()) {
    error.value = '请先粘贴一个视频链接。'
    return
  }

  if (!videoInfo.value || loadedVideoInput.value !== url.value.trim()) {
    const loaded = await loadVideoInfo()
    if (!loaded) return
  }

  if (videoInfo.value?.is_multipart && !selectedVideoUrls.value.length) {
    error.value = '请至少选择一个合集视频后再生成笔记。'
    return
  }

  loading.value = true
  result.value = null
  try {
    const response = await fetch('/api/v1/video/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        videoUrl: url.value.trim(),
        videoUrls: selectedVideoUrls.value,
        style: style.value,
        modelProvider: modelProvider.value,
        extraInstruction: extraInstruction.value.trim() || null,
      }),
    })
    const data = await response.json()
    if (!response.ok) throw new Error(data.detail || '创建任务失败，请稍后重试。')
    currentUser.value.points = data.pointsBalance
    window.localStorage.setItem(taskStorageKey(), data.taskId)
    await restoreTask(data.taskId)
  } catch (requestError) {
    error.value = requestError.message || '网络请求失败，请确认后端已经启动。'
  } finally {
    loading.value = false
  }
}

async function restoreTask(taskId) {
  try {
    const response = await fetch(`/api/v1/tasks/${taskId}`)
    const data = await response.json()
    if (!response.ok) throw new Error(data.detail || '任务不存在或已过期。')
    activeTask.value = data

    if (data.status === 'success') {
      await loadTaskNote(taskId)
      return
    }
    if (data.status === 'failed') {
      error.value = data.errorMessage || '任务未能完成，请重新尝试。'
      return
    }
    connectTaskEvents(taskId)
  } catch (taskError) {
    window.localStorage.removeItem(taskStorageKey())
    error.value = taskError.message || '恢复任务失败，请重新开始。'
  }
}

function connectTaskEvents(taskId) {
  closeTaskEvents()
  taskEvents = new EventSource(`/api/v1/tasks/${taskId}/events`)

  taskEvents.onmessage = async (event) => {
    const task = JSON.parse(event.data)
    activeTask.value = task

    if (task.status === 'success') {
      closeTaskEvents()
      await loadTaskNote(task.taskId)
      return
    }
    if (task.status === 'failed' || task.status === 'cancelled') {
      closeTaskEvents()
      window.localStorage.removeItem(taskStorageKey())
      error.value = task.errorMessage || '任务未能完成，请重新尝试。'
      await loadCurrentUser()
    }
  }
}

async function loadTaskNote(taskId) {
  try {
    const response = await fetch(`/api/v1/tasks/${taskId}/note`)
    const data = await response.json()
    if (!response.ok) throw new Error(data.detail || '笔记结果读取失败。')
    result.value = data
    currentNoteTaskId.value = taskId
    window.localStorage.removeItem(taskStorageKey())
    await loadCurrentUser()
    await loadSavedNotes()
  } catch (taskError) {
    error.value = taskError.message || '笔记结果读取失败。'
  }
}

async function loadSavedNotes() {
  try {
    const response = await fetch('/api/v1/note-groups')
    if (!response.ok) throw new Error('读取历史笔记失败。')
    savedNoteGroups.value = await response.json()
  } catch (requestError) {
    error.value = requestError.message || '读取历史笔记失败。'
  }
}

async function generateGroupedVideo(videoUrl) {
  if (!videoUrl || taskIsRunning.value) return
  updateUrl(videoUrl)
  const loaded = await loadVideoInfo()
  if (!loaded) return
  selectedVideoUrls.value = [videoUrl]
  await generateNote()
}

async function loadSavedNote(taskId) {
  try {
    const response = await fetch(`/api/v1/notes/${taskId}`)
    const data = await response.json()
    if (!response.ok) throw new Error(data.detail || '笔记读取失败。')
    closeTaskEvents()
    activeTask.value = null
    result.value = data
    currentNoteTaskId.value = taskId
    error.value = ''
  } catch (requestError) {
    error.value = requestError.message || '笔记读取失败。'
  }
}

function safePdfFileName(value) {
  const cleaned = String(value || 'AI笔记')
    .replace(/[\\/:*?"<>|]/g, '-')
    .replace(/\s+/g, ' ')
    .replace(/[. ]+$/g, '')
    .trim()
  return (cleaned || 'AI笔记').slice(0, 100)
}

async function exportGroupPdfs(group) {
  const videos = (group?.videos || [])
    .filter((video) => video.noteTaskId)
    .sort((left, right) => Number(left.page || 0) - Number(right.page || 0))
  if (!videos.length) {
    batchExportStatus.value = { groupId: group.groupId, state: 'error', text: '这个合集还没有可导出的单集笔记。' }
    return
  }
  if (!window.showDirectoryPicker) {
    batchExportStatus.value = { groupId: group.groupId, state: 'error', text: '当前浏览器不能选择文件夹，请使用最新版 Chrome 或 Edge。' }
    return
  }

  try {
    const directory = await window.showDirectoryPicker({ id: 'ainote-pdf-folder', mode: 'readwrite' })
    const numberWidth = Math.max(3, String(group.videoCount || videos.length).length)
    for (let index = 0; index < videos.length; index += 1) {
      const video = videos[index]
      batchExportStatus.value = {
        groupId: group.groupId,
        state: 'working',
        text: `正在导出 ${index + 1}/${videos.length}：${video.title}`,
      }
      const response = await fetch(`/api/v1/notes/${encodeURIComponent(video.noteTaskId)}/export/pdf`)
      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(data.detail || `“${video.title}”导出失败`)
      }
      const pageNumber = String(Number(video.page) || index + 1).padStart(numberWidth, '0')
      const fileHandle = await directory.getFileHandle(`${pageNumber}-${safePdfFileName(video.title)}.pdf`, { create: true })
      const writable = await fileHandle.createWritable()
      await writable.write(await response.blob())
      await writable.close()
    }
    batchExportStatus.value = {
      groupId: group.groupId,
      state: 'success',
      text: `已按顺序导出 ${videos.length} 份独立 PDF。`,
    }
  } catch (exportError) {
    if (exportError?.name === 'AbortError') {
      batchExportStatus.value = { groupId: '', state: '', text: '' }
      return
    }
    batchExportStatus.value = {
      groupId: group.groupId,
      state: 'error',
      text: exportError.message || '批量导出失败，请重新选择文件夹。',
    }
  }
}

function closeTaskEvents() {
  if (taskEvents) {
    taskEvents.close()
    taskEvents = null
  }
}

function resetAll() {
  closeTaskEvents()
  window.localStorage.removeItem(taskStorageKey())
  url.value = ''
  extraInstruction.value = ''
  result.value = null
  videoInfo.value = null
  loadedVideoInput.value = ''
  selectedVideoUrls.value = []
  currentNoteTaskId.value = ''
  activeTask.value = null
  error.value = ''
}

function invalidateVideoInfo() {
  videoInfo.value = null
  loadedVideoInput.value = ''
  selectedVideoUrls.value = []
  currentNoteTaskId.value = ''
  result.value = null
  error.value = ''
}

function updateUrl(value) {
  url.value = value
  invalidateVideoInfo()
}

function toSecureImageUrl(url) {
  if (!url) return ''
  if (url.startsWith('//')) return `https:${url}`
  return url.replace(/^http:\/\//i, 'https://')
}

function videoImageUrl(url) {
  const secureUrl = toSecureImageUrl(url)
  return secureUrl ? `/api/video/cover?url=${encodeURIComponent(secureUrl)}` : ''
}

onMounted(async () => {
  const authenticated = await loadCurrentUser()
  if (!authenticated) return
  await loadSavedNotes()
  const taskId = window.localStorage.getItem(taskStorageKey())
  if (taskId) restoreTask(taskId)
})

onBeforeUnmount(closeTaskEvents)
</script>

<template>
  <div v-if="authLoading" class="auth-loading"><span>▸</span><p>正在打开你的知识空间…</p></div>
  <AuthPage v-else-if="!currentUser" @authenticated="handleAuthenticated" />
  <div v-else class="workspace-shell" :class="{ 'sidebar-collapsed': sidebarCollapsed, 'notes-collapsed': noteListCollapsed }">
    <AppSidebar />
    <NoteCollectionListPage
      :active-task="activeTask"
      :result="result"
      :video-info="videoInfo"
      :groups="savedNoteGroups"
      :cover-url="videoImageUrl"
      :batch-export-status="batchExportStatus"
      @new-note="resetAll"
      @select-note="loadSavedNote"
      @generate-video="generateGroupedVideo"
      @export-group-pdfs="exportGroupPdfs"
    />
    <button
      class="workspace-toggle sidebar-toggle"
      :aria-label="sidebarCollapsed ? '展开导航栏' : '收起导航栏'"
      :title="sidebarCollapsed ? '展开导航栏' : '收起导航栏'"
      @click="sidebarCollapsed = !sidebarCollapsed"
    >{{ sidebarCollapsed ? '›' : '‹' }}</button>
    <button
      class="workspace-toggle notes-toggle"
      :aria-label="noteListCollapsed ? '展开笔记列表' : '收起笔记列表'"
      :title="noteListCollapsed ? '展开笔记列表' : '收起笔记列表'"
      @click="noteListCollapsed = !noteListCollapsed"
    >{{ noteListCollapsed ? '›' : '‹' }}</button>
    <main class="workspace-main">
      <header class="account-header">
        <div class="account-identity"><span>{{ currentUser.account.slice(0, 1).toUpperCase() }}</span><strong>{{ currentUser.account }}</strong></div>
        <div class="account-actions"><p><b>✦</b>{{ currentUser.isAdmin ? '管理员 · 无限使用' : `${currentUser.points} 积分` }}</p><button @click="logout">退出</button></div>
      </header>
      <div class="workspace-content">
        <VideoNoteComposer
          v-if="!result && !activeTask"
          :url="url"
          :style="style"
          :model-provider="modelProvider"
          :extra-instruction="extraInstruction"
          :video-info="videoInfo"
          :selected-video-urls="selectedVideoUrls"
          :loading="loading"
          :info-loading="infoLoading"
          :task-is-running="taskIsRunning"
          :error="error"
          :cover-url="videoImageUrl"
          :points="currentUser.points"
          :is-admin="currentUser.isAdmin"
          :estimated-points-cost="estimatedPointsCost"
          @update:url="updateUrl"
          @update:style="style = $event"
          @update:model-provider="modelProvider = $event"
          @update:extra-instruction="extraInstruction = $event"
          @update:selected-video-urls="selectedVideoUrls = $event"
          @load-video="loadVideoInfo"
          @generate="generateNote"
        />
        <TaskTimeline v-else-if="activeTask && !result" :task="activeTask" />
        <NoteReaderPage v-else :result="result" :note-task-id="currentNoteTaskId" :style-label="selectedStyleLabel" :cover-url="videoImageUrl" />
      </div>
    </main>
  </div>
</template>
