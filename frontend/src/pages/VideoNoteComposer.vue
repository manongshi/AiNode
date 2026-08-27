<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  url: { type: String, default: '' },
  style: { type: String, default: 'structured' },
  modelProvider: { type: String, default: 'deepseek' },
  extraInstruction: { type: String, default: '' },
  videoInfo: { type: Object, default: null },
  selectedVideoUrls: { type: Array, default: () => [] },
  loading: Boolean,
  infoLoading: Boolean,
  taskIsRunning: Boolean,
  error: { type: String, default: '' },
  coverUrl: { type: Function, required: true },
  points: { type: Number, default: 0 },
  isAdmin: Boolean,
  estimatedPointsCost: { type: Number, default: 0 },
})

const emit = defineEmits(['update:url', 'update:style', 'update:modelProvider', 'update:extraInstruction', 'update:selectedVideoUrls', 'load-video', 'generate', 'reset'])

const styles = [
  { value: 'structured', label: '结构化笔记' },
  { value: 'study', label: '学习复习' },
  { value: 'brief', label: '极简摘要' },
]
const models = [
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'qwen', label: 'Qwen 3.7' },
]

function updateUrl(event) {
  emit('update:url', event.target.value)
}

const uploadedFileName = ref('')
const sourceName = computed(() => {
  const sourceUrl = props.videoInfo?.source_url || ''
  return /(^|\.)douyin\.com|iesdouyin\.com/i.test(sourceUrl) ? '抖音视频' : 'B 站视频'
})
const videoIdentifier = computed(() => props.videoInfo?.bvid || props.videoInfo?.aid || '')
const collectionVideos = computed(() => props.videoInfo?.is_multipart ? (props.videoInfo.videos || []).filter((item) => item.url) : [])
const selectedVideoCount = computed(() => collectionVideos.value.filter((item) => props.selectedVideoUrls.includes(item.url)).length)
const isAllCollectionSelected = computed(() => collectionVideos.value.length > 0 && selectedVideoCount.value === collectionVideos.value.length)
const generateLabel = computed(() => {
  if (props.loading) return '正在创建…'
  if (props.taskIsRunning) return '任务处理中…'
  if (collectionVideos.value.length) return `生成合集笔记（${selectedVideoCount.value} 集）`
  return '生成视频笔记'
})
const pointsInsufficient = computed(() => !props.isAdmin && props.estimatedPointsCost > props.points)

function selectUpload(event) {
  uploadedFileName.value = event.target.files?.[0]?.name || ''
}

function toggleCollectionVideo(videoUrl) {
  const selected = new Set(props.selectedVideoUrls)
  if (selected.has(videoUrl)) selected.delete(videoUrl)
  else selected.add(videoUrl)
  emit('update:selectedVideoUrls', collectionVideos.value.filter((item) => selected.has(item.url)).map((item) => item.url))
}

function toggleAllCollectionVideos() {
  emit('update:selectedVideoUrls', isAllCollectionSelected.value ? [] : collectionVideos.value.map((item) => item.url))
}
</script>

<template>
  <section class="composer-page">
    <div v-if="!videoInfo" class="composer-hero">
      <span class="trial-badge">✦ 视频内容，一键整理为你的知识</span>
      <h1>粘贴视频链接<br />生成 <em>AI 笔记</em></h1>
      <p>支持从视频平台链接或本地视频开始整理，生成带目录的文档笔记。</p>
    </div>

    <div v-else class="video-confirmation">
      <div class="confirmation-cover"><img v-if="videoInfo.cover" :src="coverUrl(videoInfo.cover)" alt="视频封面" /><span v-else>VIDEO</span></div>
      <div class="confirmation-copy">
        <span>{{ sourceName }} · 视频信息已读取</span>
        <h1>{{ videoInfo.title || '未命名视频' }}</h1>
        <p>{{ videoInfo.owner?.name || '未知作者' }} · {{ videoInfo.duration_text || '时长未知' }}<template v-if="videoIdentifier"> · 编号 {{ videoIdentifier }}</template></p>
        <a v-if="videoInfo.source_url" :href="videoInfo.source_url" target="_blank" rel="noopener noreferrer">查看原视频 ↗</a>
      </div>
    </div>

    <section v-if="collectionVideos.length" class="collection-preview">
      <header>
        <div>
          <span>视频合集</span>
          <strong>共 {{ collectionVideos.length }} 集，已选择 {{ selectedVideoCount }} 集</strong>
        </div>
        <button type="button" @click="toggleAllCollectionVideos">{{ isAllCollectionSelected ? '取消全选' : '全选全部' }}</button>
      </header>
      <div class="collection-video-list" aria-label="合集视频列表">
        <label v-for="video in collectionVideos" :key="video.url" class="collection-video-item">
          <input type="checkbox" :checked="selectedVideoUrls.includes(video.url)" @change="toggleCollectionVideo(video.url)" />
          <span class="collection-page">P{{ video.page }}</span>
          <span class="collection-video-title">{{ video.title || `第 ${video.page} 集` }}</span>
          <time>{{ video.duration_text || '时长未知' }}</time>
        </label>
      </div>
    </section>

    <div class="composer-box">
      <label class="url-input">
        <input :value="url" type="text" placeholder="粘贴视频链接或抖音分享文案（支持 B 站、抖音等平台）" :disabled="taskIsRunning" @input="updateUrl" @keyup.enter="$emit('load-video')" />
        <button :disabled="infoLoading || loading || taskIsRunning" @click="$emit('load-video')">{{ infoLoading ? '读取中…' : '读取视频' }}</button>
      </label>
      <label class="upload-input"><span>⇧</span><strong>{{ uploadedFileName || '或上传本地视频' }}</strong><small>{{ uploadedFileName ? '已选择文件，等待接入上传与转写逻辑' : '支持 MP4、MOV、WebM' }}</small><input type="file" accept="video/*" @change="selectUpload" /></label>
      <div class="composer-options">
        <div class="style-select"><span>笔记格式</span><button v-for="option in styles" :key="option.value" :class="{ selected: style === option.value }" @click="$emit('update:style', option.value)">{{ option.label }}</button></div>
        <div class="model-select"><span>AI 模型</span><button v-for="model in models" :key="model.value" :class="{ selected: modelProvider === model.value }" @click="$emit('update:modelProvider', model.value)">{{ model.label }}</button></div>
        <input class="focus-input" :value="extraInstruction" placeholder="可选：特别关注的内容" @input="$emit('update:extraInstruction', $event.target.value)" />
      </div>
      <div v-if="videoInfo" class="points-preview" :class="{ insufficient: pointsInsufficient }">
        <span><b>✦</b> {{ isAdmin ? '管理员任务不扣积分' : `本次预计 ${estimatedPointsCost} 积分` }}</span>
        <small>{{ isAdmin ? '无限使用' : pointsInsufficient ? `当前仅剩 ${points} 积分` : `生成后预计剩余 ${points - estimatedPointsCost} 积分` }}</small>
      </div>
      <button class="generate-note" :disabled="loading || infoLoading || taskIsRunning || pointsInsufficient || (collectionVideos.length && !selectedVideoCount)" @click="$emit('generate')">{{ generateLabel }} <span>→</span></button>
    </div>

    <p v-if="error" class="composer-error">{{ error }}</p>
    <p class="composer-tip">没有字幕的视频会自动提取音频并转写；每开始 1 分钟消耗 1 积分，任务失败会自动退回。</p>
  </section>
</template>

<style scoped>
.composer-page { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: min(760px, calc(100vh - 62px)); padding: 54px 30px; }
.composer-hero { max-width: 850px; text-align: center; }
.trial-badge { display: inline-block; padding: 8px 18px; color: #4f8c42; background: #f0f9e8; border: 1px solid #d7efc5; border-radius: 99px; font-size: 13px; font-weight: 700; }
.composer-hero h1, .video-confirmation h1 { margin: 27px 0 16px; color: #111a2c; font-size: clamp(36px, 4.5vw, 58px); letter-spacing: -.07em; line-height: 1.12; }
.composer-hero h1 em { color: #3e72ef; font-style: normal; }
.composer-hero p { margin: 0; color: #718098; font-size: 17px; }
.composer-box { display: flex; flex-wrap: wrap; gap: 13px; width: min(760px, 100%); margin-top: 42px; padding: 13px; background: #fff; border: 1px solid #e4e9f3; border-radius: 15px; box-shadow: 0 16px 45px rgba(54, 77, 125, .09); }
.url-input { display: flex; flex: 1 1 480px; gap: 10px; min-width: 0; padding: 0 9px 0 15px; background: #f7f9fe; border: 1px solid #e7ecf7; border-radius: 10px; }
.url-input input { min-width: 0; flex: 1; height: 55px; color: #27334a; background: transparent; border: 0; outline: 0; font-size: 15px; }
.url-input button, .generate-note { color: #fff; background: #3e72ef; border: 0; border-radius: 9px; font-size: 14px; font-weight: 700; }
.url-input button { align-self: center; height: 39px; padding: 0 14px; }
.composer-options { display: flex; flex: 1 1 100%; gap: 11px; align-items: center; }
.style-select, .model-select { display: flex; gap: 5px; align-items: center; color: #8490a2; font-size: 12px; white-space: nowrap; }
.style-select button, .model-select button { padding: 6px 9px; color: #718098; background: #f7f8fb; border: 1px solid #e9ecf2; border-radius: 6px; font-size: 11px; }
.style-select button.selected, .model-select button.selected { color: #3168e7; background: #edf3ff; border-color: #cbdcff; }
.model-select { padding-left: 10px; border-left: 1px solid #e6eaf1; }
.focus-input { min-width: 160px; flex: 1; padding: 7px 10px; color: #556278; background: #f7f8fb; border: 1px solid #e9ecf2; border-radius: 6px; outline: 0; font-size: 12px; }
.generate-note { flex: 0 0 150px; min-height: 55px; box-shadow: 0 7px 15px rgba(62, 114, 239, .22); }
.generate-note span { margin-left: 7px; font-size: 17px; }
.url-input button:hover:not(:disabled), .generate-note:hover:not(:disabled) { background: #295edc; }
button:disabled { cursor: wait; opacity: .65; }
.composer-tip { margin: 16px 0 0; color: #a3acbb; font-size: 11px; text-align: center; }
.composer-error { margin: 14px 0 0; color: #cf5c52; font-size: 12px; }
.points-preview { display: flex; flex: 1 1 100%; align-items: center; justify-content: space-between; padding: 10px 12px; color: #72511d; background: #fff9ee; border: 1px solid #f2dfbd; border-radius: 8px; font-size: 11px; }.points-preview b { color: #e29422; }.points-preview small { color: #9a825c; }.points-preview.insufficient { color: #a64c45; background: #fff4f2; border-color: #f1d0cb; }.points-preview.insufficient small { color: #b66a63; }
.video-confirmation { display: flex; align-items: center; gap: 20px; width: min(700px, 100%); padding: 16px; background: #fff; border: 1px solid #e3e9f5; border-radius: 13px; box-shadow: 0 12px 30px rgba(54, 77, 125, .07); }
.confirmation-cover { display: grid; flex: 0 0 auto; width: 132px; height: 82px; overflow: hidden; place-items: center; color: #386ee8; background: #ecf2ff; border-radius: 8px; font-size: 11px; font-weight: 800; }
.confirmation-cover img { width: 100%; height: 100%; object-fit: cover; }
.video-confirmation span { color: #4b7ceb; font-size: 11px; font-weight: 700; }
.video-confirmation h1 { margin: 5px 0; overflow: hidden; font-size: 20px; text-overflow: ellipsis; white-space: nowrap; }
.video-confirmation p { margin: 0; color: #92a0b5; font-size: 12px; }
.confirmation-copy { min-width: 0; }
.confirmation-copy a { display: inline-block; margin-top: 8px; color: #326fe8; font-size: 11px; font-weight: 700; text-decoration: none; }
.confirmation-copy a:hover { text-decoration: underline; }
.collection-preview { width: min(700px, 100%); margin-top: 15px; overflow: hidden; background: #fff; border: 1px solid #e3e9f5; border-radius: 13px; box-shadow: 0 12px 30px rgba(54, 77, 125, .05); }
.collection-preview header { display: flex; justify-content: space-between; gap: 16px; align-items: center; padding: 13px 16px; border-bottom: 1px solid #edf0f6; }
.collection-preview header div { display: flex; gap: 8px; align-items: center; min-width: 0; }
.collection-preview header span { color: #3e72ef; font-size: 11px; font-weight: 800; }
.collection-preview header strong { overflow: hidden; color: #536178; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.collection-preview header button { flex: 0 0 auto; padding: 5px 8px; color: #3970e8; background: #f0f5ff; border: 1px solid #d5e2ff; border-radius: 6px; font-size: 11px; font-weight: 700; }
.collection-video-list { max-height: 190px; overflow-y: auto; }
.collection-video-item { display: grid; grid-template-columns: 16px 34px minmax(0, 1fr) 54px; gap: 9px; align-items: center; padding: 10px 16px; color: #536178; border-bottom: 1px solid #f0f3f7; cursor: pointer; }
.collection-video-item:last-child { border-bottom: 0; }
.collection-video-item input { width: 14px; height: 14px; accent-color: #3e72ef; }
.collection-page { color: #3e72ef; font-size: 11px; font-weight: 800; }
.collection-video-title { overflow: hidden; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.collection-video-item time { color: #9aa8bb; font-size: 10px; text-align: right; }
.upload-input { display: flex; flex: 1 1 100%; gap: 7px; align-items: center; justify-content: center; min-height: 43px; color: #6680a8; background: #f9fbff; border: 1px dashed #b9ccef; border-radius: 10px; text-align: center; }
.upload-input span { color: #3e72ef; font-size: 19px; line-height: 1; }
.upload-input strong { font-size: 12px; }
.upload-input small { color: #9aa8bb; font-size: 10px; }
.upload-input input { display: none; }

@media (max-width: 600px) { .composer-page { min-height: auto; padding: 70px 20px; } .composer-hero h1 { font-size: 38px; } .composer-hero p { font-size: 14px; line-height: 1.7; } .composer-box { margin-top: 30px; } .composer-options { align-items: stretch; flex-direction: column; } .style-select { flex-wrap: wrap; } .model-select { padding: 8px 0 0; border-top: 1px solid #e6eaf1; border-left: 0; }.generate-note { flex-basis: 100%; } .video-confirmation { align-items: flex-start; } .confirmation-cover { width: 84px; height: 58px; } .video-confirmation h1 { white-space: normal; font-size: 16px; } }
</style>
