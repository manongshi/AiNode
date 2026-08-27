<script setup>
import { Markmap } from 'markmap-view'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  mindMap: { type: Object, default: () => ({}) },
})

const svgElement = ref(null)
let markmap = null

async function renderMindMap() {
  if (!props.mindMap?.content || !svgElement.value) return
  await nextTick()
  const options = {
    autoFit: true,
    duration: 300,
    fitRatio: 0.9,
    maxWidth: 220,
    spacingHorizontal: 100,
    spacingVertical: 12,
    pan: true,
    zoom: true,
    color: (node) => ['#4b7ef4', '#7b64d8', '#39a995', '#db9f35'][Math.max(0, node.state.depth - 1) % 4],
  }
  if (!markmap) {
    markmap = Markmap.create(svgElement.value, options, props.mindMap)
    return
  }
  await markmap.setData(props.mindMap, options)
  await markmap.fit()
}

onMounted(renderMindMap)
onBeforeUnmount(() => markmap?.destroy())
watch(() => props.mindMap, renderMindMap, { deep: true })
</script>

<template>
  <section class="mind-map-view">
    <svg v-if="mindMap?.content" ref="svgElement" class="markmap-svg" aria-label="思维导图"></svg>
    <div v-else class="mind-map-empty">这篇历史笔记暂未生成 Markmap 思维导图。</div>
  </section>
</template>

<style scoped>
.mind-map-view { position: relative; flex: 1; min-height: 0; overflow: hidden; background: #fbfcff; }
.markmap-svg { width: 100%; height: 100%; min-height: 580px; background: radial-gradient(circle at 50% 50%, #fff 0, #f7f9ff 80%); }
.mind-map-empty { display: grid; height: 100%; place-items: center; color: #9aa8ba; font-size: 13px; }
</style>
