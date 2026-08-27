<script setup>
import { computed } from 'vue'

const props = defineProps({
  activeTask: { type: Object, default: null },
  result: { type: Object, default: null },
  videoInfo: { type: Object, default: null },
  notes: { type: Array, default: () => [] },
  coverUrl: { type: Function, required: true },
})

defineEmits(['new-note', 'select-note'])

const taskIsRunning = computed(() => ['pending', 'running'].includes(props.activeTask?.status))
</script>

<template>
  <aside class="note-list-panel">
    <header class="list-header"><h2>笔记</h2><button title="收起列表">☷</button></header>
    <button class="new-note-button" @click="$emit('new-note')">＋ 新建笔记</button>
    <label class="note-search"><span>⌕</span><input placeholder="搜索笔记…" /></label>

    <div class="list-body">
      <template v-if="activeTask || result || videoInfo || notes.length">
        <p class="list-section-title"><i></i>{{ taskIsRunning ? '进行中' : '最近笔记' }}</p>
        <article v-if="activeTask || result || videoInfo" class="note-row selected">
          <div class="row-cover">
            <img v-if="(result?.video || videoInfo)?.cover" :src="coverUrl((result?.video || videoInfo).cover)" alt="视频封面" />
            <span v-else>AI</span>
          </div>
          <div class="row-copy">
            <strong>{{ result?.video?.title || videoInfo?.title || '正在创建新笔记' }}</strong>
            <span v-if="taskIsRunning" class="processing">{{ activeTask.currentStep === 'generate_note' ? '正在生成' : '正在处理' }}</span>
            <span v-else class="completed">已完成</span>
          </div>
        </article>
        <article v-for="note in notes.filter((item) => item.taskId !== activeTask?.taskId)" :key="note.taskId" class="note-row" @click="$emit('select-note', note.taskId)">
          <div class="row-cover">
            <img v-if="note.cover" :src="coverUrl(note.cover)" alt="视频封面" />
            <span v-else>AI</span>
          </div>
          <div class="row-copy">
            <strong>{{ note.title }}</strong>
            <span>{{ note.createdAt }}</span>
          </div>
        </article>
      </template>
      <div v-else class="list-empty"><span>▱</span><p>你的第一篇笔记<br />会出现在这里</p></div>
    </div>
  </aside>
</template>

<style scoped>
.note-list-panel { display: flex; flex-direction: column; min-height: 100vh; background: #fff; border-right: 1px solid #e7ebf3; }
.list-header { display: flex; align-items: center; justify-content: space-between; min-height: 68px; padding: 0 16px; border-bottom: 1px solid #edf0f5; }
.list-header h2 { margin: 0; color: #3c4657; font-size: 16px; }
.list-header button { color: #8c96a6; background: transparent; border: 0; font-size: 19px; }
.new-note-button { width: calc(100% - 32px); min-height: 44px; margin: 16px; color: #fff; background: #3e72ef; border: 0; border-radius: 8px; font-size: 14px; font-weight: 700; box-shadow: 0 5px 12px rgba(62, 114, 239, .2); }
.note-search { display: flex; gap: 7px; align-items: center; margin: 0 16px 16px; padding: 0 11px; color: #a5adba; background: #f7f8fa; border: 1px solid #eaedf2; border-radius: 7px; }
.note-search input { width: 100%; height: 35px; color: #374151; background: transparent; border: 0; outline: 0; font-size: 12px; }
.note-search input::placeholder { color: #b4bbc6; }
.list-body { flex: 1; border-top: 1px solid #edf0f5; }
.list-section-title { display: flex; gap: 6px; align-items: center; margin: 12px 16px 7px; color: #4a77ef; font-size: 12px; font-weight: 700; }
.list-section-title i { width: 7px; height: 7px; background: #70a3ff; border-radius: 50%; }
.note-row { display: flex; gap: 10px; padding: 12px 16px; border-left: 3px solid transparent; cursor: pointer; }
.note-row:hover { background: #f6f8fc; }
.note-row.selected { background: #eff4ff; border-left-color: #3c73f4; }
.row-cover { display: grid; flex: 0 0 auto; width: 50px; height: 40px; overflow: hidden; place-items: center; color: #4f79eb; background: #e1eaff; border-radius: 4px; font-size: 10px; font-weight: 800; }
.row-cover img { width: 100%; height: 100%; object-fit: cover; }
.row-copy { min-width: 0; }
.row-copy strong { display: -webkit-box; overflow: hidden; color: #3b4657; font-size: 12px; line-height: 1.4; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.row-copy span { display: block; margin-top: 4px; color: #a0a9b5; font-size: 10px; }
.row-copy .processing { color: #ec951c; }
.row-copy .completed { color: #2a9a68; }
.list-empty { display: grid; place-items: center; min-height: 340px; color: #c5cad2; text-align: center; }
.list-empty span { font-size: 42px; opacity: .45; }
.list-empty p { margin: 9px 0 0; font-size: 12px; line-height: 1.8; }

@media (max-width: 1180px) { .note-list-panel { display: none; } }
</style>
