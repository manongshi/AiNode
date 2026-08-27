<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps({
  task: {
    type: Object,
    required: true,
  },
})

const taskStatusText = computed(() => {
  if (props.task.status === 'pending') return '任务已创建，正在排队'
  if (props.task.status === 'running') return '正在整理视频内容'
  if (props.task.status === 'success') return '笔记整理完成'
  if (props.task.status === 'failed') return '任务未能完成'
  return '任务状态未知'
})

const elapsedSeconds = ref(1)
let elapsedTimer = null

function stopTimer() {
  if (elapsedTimer) {
    window.clearInterval(elapsedTimer)
    elapsedTimer = null
  }
}

function startTimer() {
  stopTimer()
  elapsedSeconds.value = 1
  elapsedTimer = window.setInterval(() => {
    elapsedSeconds.value += 1
  }, 1000)
}

watch(
  () => {
    const step = props.task.steps.find((item) => item.key === props.task.currentStep)
    return step?.status === 'running' ? step.key : ''
  },
  (currentStep, previousStep) => {
    if (currentStep) startTimer()
    else if (previousStep) stopTimer()
  },
  { immediate: true },
)

onBeforeUnmount(stopTimer)

function stepIcon(status) {
  if (status === 'success') return '✓'
  if (status === 'skipped') return '–'
  if (status === 'failed') return '!'
  if (status === 'running') return '…'
  return ''
}
</script>

<template>
  <section class="task-timeline-state">
    <header class="timeline-heading">
      <div>
        <p class="timeline-kicker">TASK / {{ task.taskId.slice(0, 8) }}</p>
        <h2>{{ taskStatusText }}</h2>
      </div>
      <div class="timeline-percent">{{ task.progress }}<small>%</small></div>
    </header>

    <div class="timeline-scroll">
      <ol class="timeline-steps">
        <li
          v-for="(step, index) in task.steps"
          :key="step.key"
          :class="[`is-${step.status}`, { current: step.key === task.currentStep }]"
        >
          <span v-if="index < task.steps.length - 1" class="timeline-connector"></span>
          <span class="timeline-node">{{ stepIcon(step.status) }}</span>
          <div class="timeline-copy">
            <strong>{{ step.label }}</strong>
            <span v-if="step.key === task.currentStep && step.status === 'running'">{{ elapsedSeconds }}s</span>
          </div>
        </li>
      </ol>
    </div>

  </section>
</template>

<style scoped>
.task-timeline-state { min-height: 610px; padding: 8% 10%; animation: fade-in .35s ease; }
.timeline-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; }
.timeline-kicker { margin: 0; color: #4c7ff3; font-size: 10px; font-weight: 800; letter-spacing: .14em; }
.timeline-heading h2 { max-width: 480px; margin: 11px 0 0; color: #1b2640; font-family: "Songti SC", "STSong", Georgia, serif; font-size: clamp(29px, 3.5vw, 47px); font-weight: 700; letter-spacing: -.07em; line-height: 1.08; }
.timeline-percent { display: flex; align-items: baseline; color: #3e72ef; font-size: clamp(34px, 5vw, 55px); font-weight: 800; letter-spacing: -.08em; line-height: .9; }
.timeline-percent small { margin-left: 3px; font-size: 15px; letter-spacing: 0; }
.timeline-scroll { margin: 58px -8px 0; overflow-x: auto; padding: 8px; }
.timeline-steps { display: flex; min-width: max-content; margin: 0; padding: 0; list-style: none; }
.timeline-steps li { position: relative; display: grid; grid-template-rows: 32px auto; width: clamp(115px, 14vw, 158px); padding-right: 13px; }
.timeline-node { z-index: 1; display: grid; width: 27px; height: 27px; place-items: center; color: #9da8bb; background: #fff; border: 2px solid #d9dfeb; border-radius: 50%; font-size: 13px; font-weight: 800; }
.timeline-connector { position: absolute; top: 13px; left: 27px; width: calc(100% - 27px); height: 2px; background: #e4e8f0; }
.timeline-copy { padding-top: 10px; }
.timeline-copy strong, .timeline-copy span { display: block; max-width: 145px; }
.timeline-copy strong { color: #526178; font-size: 12px; line-height: 1.4; }
.timeline-copy span { margin-top: 4px; color: #9da8b8; font-size: 10px; line-height: 1.5; }
.is-success .timeline-node { color: #fff; background: #3e72ef; border-color: #3e72ef; }
.is-success .timeline-connector { background: #76a0fa; }
.is-skipped .timeline-node { color: #7d8ba1; background: #f1f4f8; border-color: #dfe5ed; }
.is-running .timeline-node { color: #fff; background: #3e72ef; border-color: #3e72ef; box-shadow: 0 0 0 5px rgba(112, 153, 251, .25); animation: node-pulse 1.3s ease-in-out infinite; }
.current .timeline-copy strong { color: #2e65e3; }
.current .timeline-copy span { color: #4c7ff3; }
.is-failed .timeline-node { color: #fff; background: #d95e51; border-color: #d95e51; }
@keyframes fade-in { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
@keyframes node-pulse { 0%, 100% { box-shadow: 0 0 0 5px rgba(112, 153, 251, .25); } 50% { box-shadow: 0 0 0 9px rgba(112, 153, 251, 0); } }

@media (max-width: 600px) {
  .task-timeline-state { min-height: 500px; padding: 13% 9%; }
  .timeline-scroll { margin-top: 42px; }
}
</style>
