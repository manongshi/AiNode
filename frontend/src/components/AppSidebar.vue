<template>
  <aside class="app-sidebar">
    <div class="app-logo">
      <span class="logo-mark">▸</span>
      <span>AiNote</span>
      <small>AI</small>
    </div>

    <nav class="primary-nav" aria-label="主导航">
      <button class="nav-item active"><span>⌂</span>工作台</button>
    </nav>

    <div class="sidebar-bottom">
      <button class="nav-item"><span>?</span>使用帮助</button>
      <div class="credit-card"><b>✦</b><span><strong>AI 笔记</strong><small>视频内容整理</small></span></div>
    </div>
  </aside>
</template>

<style scoped>
.app-sidebar { display: flex; flex-direction: column; min-height: 100vh; padding: 22px 10px 14px; background: #fff; border-right: 1px solid #e7ebf3; }
.app-logo { display: flex; align-items: center; gap: 9px; padding: 0 8px 24px; color: #15233c; font-size: 21px; font-weight: 800; letter-spacing: -.05em; }
.logo-mark { display: grid; width: 36px; height: 36px; place-items: center; color: #fff; background: linear-gradient(135deg, #4c83ff, #2864eb); border-radius: 9px; font-size: 22px; transform: rotate(180deg); }
.app-logo small { padding: 2px 5px; color: #dd7b14; background: #fff2dc; border: 1px solid #ffd7a4; border-radius: 4px; font-size: 10px; letter-spacing: 0; }
.primary-nav { display: grid; gap: 5px; }
.nav-item { display: flex; gap: 12px; align-items: center; width: 100%; min-height: 42px; padding: 0 10px; color: #5e6b7e; background: transparent; border: 0; border-radius: 8px; font-size: 14px; font-weight: 600; text-align: left; }
.nav-item span { width: 21px; color: #5b718e; font-size: 20px; font-weight: 400; text-align: center; }
.nav-item:hover { color: #2864eb; background: #f3f6ff; }
.nav-item.active { color: #2864eb; background: #edf3ff; box-shadow: inset 3px 0 #3e78f9; }
.nav-item.active span { color: #2864eb; }
.sidebar-bottom { display: grid; gap: 10px; margin-top: auto; }
.credit-card { display: flex; gap: 10px; align-items: center; padding: 13px; color: #dce8ff; background: #17233b; border-radius: 10px; }
.credit-card b { display: grid; width: 30px; height: 30px; place-items: center; color: #fff; background: #4b7eff; border-radius: 50%; }
.credit-card strong, .credit-card small { display: block; }
.credit-card strong { font-size: 12px; }
.credit-card small { margin-top: 3px; color: #91a2c2; font-size: 10px; }

@media (max-width: 980px) {
  .app-sidebar { display: none; }
}
</style>
