<script setup>
defineProps({
  html: {
    type: String,
    default: '',
  },
})
</script>

<template>
  <article class="word-document">
    <div class="document-page">
      <div class="document-topline">
        <span>AI NOTE</span>
        <span>阅读视图</span>
      </div>
      <div class="document-prose" v-html="html"></div>
    </div>
  </article>
</template>

<style scoped>
.word-document { min-width: 0; }
.document-page { min-height: 700px; padding: clamp(28px, 4vw, 62px); background: #fff; border: 1px solid #e2eae5; box-shadow: 0 17px 42px rgba(47, 76, 62, .1); }
.document-topline { display: flex; justify-content: space-between; padding-bottom: 15px; color: #749487; border-bottom: 2px solid #2a936d; font-size: 10px; font-weight: 800; letter-spacing: .12em; }
.document-prose { max-width: 810px; margin: 34px auto 0; color: #273e34; font-family: "Songti SC", "STSong", "Noto Serif CJK SC", serif; font-size: 16px; line-height: 2; }
.document-prose :deep(> :first-child) { margin-top: 0; }
.document-prose :deep(h1), .document-prose :deep(h2), .document-prose :deep(h3), .document-prose :deep(h4) { scroll-margin-top: 24px; color: #173e30; font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif; line-height: 1.4; }
.document-prose :deep(h1) { margin: 0 0 30px; padding-bottom: 18px; border-bottom: 1px solid #dae7df; font-size: clamp(25px, 3vw, 36px); letter-spacing: -.055em; }
.document-prose :deep(h2) { margin: 48px 0 20px; padding: 10px 0 10px 16px; border-left: 5px solid #2c966f; font-size: 22px; letter-spacing: -.035em; }
.document-prose :deep(h3) { margin: 34px 0 13px; font-size: 18px; }
.document-prose :deep(h4) { margin: 25px 0 10px; color: #36735d; font-size: 16px; }
.document-prose :deep(p) { margin: 13px 0; }
.document-prose :deep(ul), .document-prose :deep(ol) { margin: 15px 0; padding-left: 28px; }
.document-prose :deep(li + li) { margin-top: 8px; }
.document-prose :deep(li::marker) { color: #2f936d; font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-weight: 800; }
.document-prose :deep(strong) { color: #176647; font-family: -apple-system, BlinkMacSystemFont, sans-serif; }
.document-prose :deep(blockquote) { margin: 20px 0; padding: 13px 18px; color: #547167; background: #f1f8f3; border-left: 3px solid #9bceb5; }
.document-prose :deep(hr) { margin: 35px 0; border: 0; border-top: 1px solid #dbe6df; }
.document-prose :deep(code) { padding: 2px 5px; color: #175b43; background: #eaf5ef; border-radius: 3px; font-family: "SFMono-Regular", Consolas, monospace; font-size: .88em; }
.document-prose :deep(pre) { padding: 18px; overflow-x: auto; color: #dcece3; background: #193c30; border-radius: 4px; line-height: 1.7; }
.document-prose :deep(pre code) { padding: 0; color: inherit; background: transparent; }
.document-prose :deep(table) { width: 100%; margin: 22px 0; border-collapse: collapse; font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif; font-size: 13px; line-height: 1.65; }
.document-prose :deep(th), .document-prose :deep(td) { padding: 10px 12px; text-align: left; border: 1px solid #d9e6df; }
.document-prose :deep(th) { color: #245d49; background: #edf7f0; font-weight: 800; }
.document-prose :deep(a) { color: #137756; text-decoration-color: #96cdb5; }

@media (max-width: 600px) {
  .document-page { min-height: 0; padding: 27px 20px 38px; }
  .document-prose { margin-top: 24px; font-size: 15px; line-height: 1.9; }
  .document-prose :deep(h2) { margin-top: 38px; font-size: 20px; }
  .document-prose :deep(table) { display: block; overflow-x: auto; }
}
</style>
