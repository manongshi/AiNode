<script setup>
defineProps({
  items: {
    type: Array,
    default: () => [],
  },
  activeId: {
    type: String,
    default: '',
  },
})

defineEmits(['select'])
</script>

<template>
  <aside class="note-outline" aria-label="笔记目录">
    <div class="outline-heading">
      <span class="outline-kicker">CONTENTS</span>
      <h3>目录</h3>
    </div>
    <nav v-if="items.length" class="outline-nav">
      <button
        v-for="item in items"
        :key="item.id"
        class="outline-item"
        :class="{ active: item.id === activeId, 'is-title': item.level === 1 }"
        :style="{ '--outline-indent': `${Math.max(0, item.level - 1) * 13}px` }"
        @click="$emit('select', item.id)"
      >
        <span class="outline-dot"></span>
        <span>{{ item.title }}</span>
      </button>
    </nav>
    <p v-else class="outline-empty">正在生成目录…</p>
  </aside>
</template>

<style scoped>
.note-outline { min-height: 0; padding: 3px 22px 28px 0; overflow-y: auto; border-right: 1px solid #dce8e2; }
.outline-heading { margin-bottom: 16px; }
.outline-kicker { color: #2e9371; font-size: 10px; font-weight: 800; letter-spacing: .14em; }
.outline-heading h3 { margin: 3px 0 0; color: #1f3f34; font-size: 20px; letter-spacing: -.04em; }
.outline-nav { display: grid; gap: 3px; }
.outline-item { display: flex; align-items: flex-start; gap: 8px; width: 100%; padding: 7px 4px 7px calc(var(--outline-indent) + 4px); color: #738b81; background: transparent; border: 0; border-radius: 5px; font: inherit; font-size: 12px; line-height: 1.45; text-align: left; cursor: pointer; }
.outline-item:hover, .outline-item.active { color: #176f52; background: #eaf5ef; }
.outline-item.is-title { color: #2c4e41; font-weight: 800; }
.outline-dot { flex: 0 0 auto; width: 5px; height: 5px; margin-top: 6px; background: #bed8ca; border-radius: 50%; }
.outline-item.active .outline-dot { background: #25946c; box-shadow: 0 0 0 3px #cfe9da; }
.outline-empty { margin: 0; color: #98aaa1; font-size: 12px; }

@media (max-width: 880px) {
  .note-outline { padding: 0 0 15px; overflow: visible; border-right: 0; border-bottom: 1px solid #dce8e2; }
  .outline-nav { display: flex; gap: 7px; overflow-x: auto; padding-bottom: 3px; }
  .outline-item { flex: 0 0 auto; width: auto; padding: 7px 10px; white-space: nowrap; }
  .outline-item .outline-dot { display: none; }
}
</style>
