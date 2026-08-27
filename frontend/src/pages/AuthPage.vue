<script setup>
import { computed, ref } from 'vue'

const emit = defineEmits(['authenticated'])

const mode = ref('login')
const account = ref('')
const email = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

const isRegister = computed(() => mode.value === 'register')

function switchMode(nextMode) {
  mode.value = nextMode
  error.value = ''
}

async function submit() {
  error.value = ''
  if (!account.value.trim()) {
    error.value = isRegister.value ? '请输入账号。' : '请输入账号或邮箱。'
    return
  }
  if (isRegister.value && !email.value.trim()) {
    error.value = '请输入邮箱。'
    return
  }
  if (!password.value) {
    error.value = '请输入密码。'
    return
  }

  loading.value = true
  try {
    const endpoint = isRegister.value ? '/api/auth/register' : '/api/auth/login'
    const payload = isRegister.value
      ? { account: account.value.trim(), email: email.value.trim(), password: password.value }
      : { login: account.value.trim(), password: password.value }
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    const data = await response.json()
    const detail = Array.isArray(data.detail) ? data.detail[0]?.msg : data.detail
    if (!response.ok) throw new Error(detail || '暂时无法进入，请稍后重试。')
    emit('authenticated', data)
  } catch (requestError) {
    error.value = requestError.message || '网络连接失败，请确认服务已经启动。'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="auth-page">
    <section class="auth-story" aria-label="AiNote 产品介绍">
      <div class="auth-brand"><span>▸</span><strong>AiNote</strong><small>VIDEO → KNOWLEDGE</small></div>
      <div class="story-copy">
        <p class="story-kicker">把播放时间，变成可检索的知识</p>
        <h1>视频会结束，<br /><em>理解</em>可以留下。</h1>
        <p class="story-note">从字幕、章节到思维导图，AiNote 帮你把视频里的重要内容整理成真正能再次使用的笔记。</p>
      </div>
      <div class="timeline-signature" aria-hidden="true">
        <span class="time-code">00:00</span>
        <div class="timeline-track"><i></i><b></b><b></b><b></b></div>
        <div class="timeline-notes">
          <span>识别主题</span><span>整理章节</span><span>沉淀观点</span>
        </div>
      </div>
    </section>

    <section class="auth-panel">
      <div class="auth-card">
        <header>
          <span class="welcome-mark">A</span>
          <div><p>{{ isRegister ? '创建你的知识空间' : '欢迎回来' }}</p><h2>{{ isRegister ? '注册 AiNote' : '登录 AiNote' }}</h2></div>
        </header>

        <div class="auth-tabs" role="tablist" aria-label="登录或注册">
          <button :class="{ active: mode === 'login' }" @click="switchMode('login')">登录</button>
          <button :class="{ active: mode === 'register' }" @click="switchMode('register')">注册</button>
        </div>

        <form @submit.prevent="submit">
          <label>
            <span>{{ isRegister ? '账号' : '账号或邮箱' }}</span>
            <input v-model="account" :autocomplete="isRegister ? 'username' : 'username'" :placeholder="isRegister ? '3–32 位，支持中文、字母和数字' : '输入你的账号或邮箱'" />
          </label>
          <label v-if="isRegister">
            <span>邮箱</span>
            <input v-model="email" type="email" autocomplete="email" placeholder="name@example.com" />
          </label>
          <label>
            <span>密码</span>
            <input v-model="password" type="password" :autocomplete="isRegister ? 'new-password' : 'current-password'" :placeholder="isRegister ? '至少 8 位字符' : '输入密码'" />
          </label>
          <p v-if="error" class="auth-error">{{ error }}</p>
          <button class="auth-submit" :disabled="loading">
            {{ loading ? '正在进入…' : isRegister ? '注册并领取 100 积分' : '进入工作台' }} <span>→</span>
          </button>
        </form>

        <p class="register-gift"><b>100</b><span>新账号初始积分<br /><small>视频每开始 1 分钟消耗 1 积分</small></span></p>
      </div>
    </section>
  </main>
</template>

<style scoped>
.auth-page { --ink: #15223a; --blue: #356ff1; --mist: #eef4ff; --amber: #e89b2d; display: grid; grid-template-columns: minmax(0, 1.08fr) minmax(440px, .92fr); min-height: 100vh; color: var(--ink); background: #f7f9fd; }
.auth-story { position: relative; display: flex; flex-direction: column; min-height: 100vh; overflow: hidden; padding: 44px clamp(40px, 7vw, 108px) 54px; background: #eaf1ff; }
.auth-story::after { position: absolute; right: -15%; bottom: -35%; width: 620px; height: 620px; border: 1px solid rgba(53,111,241,.18); border-radius: 50%; box-shadow: 0 0 0 70px rgba(53,111,241,.035), 0 0 0 150px rgba(53,111,241,.025); content: ''; }
.auth-brand { display: flex; align-items: center; gap: 10px; font-size: 22px; letter-spacing: -.05em; }
.auth-brand > span { display: grid; width: 38px; height: 38px; place-items: center; color: #fff; background: var(--blue); border-radius: 11px; transform: rotate(180deg); }
.auth-brand small { margin-left: 8px; color: #7183a5; font-size: 9px; font-weight: 800; letter-spacing: .13em; }
.story-copy { position: relative; z-index: 1; max-width: 690px; margin: auto 0 52px; }
.story-kicker { margin: 0 0 20px; color: var(--blue); font-size: 13px; font-weight: 800; letter-spacing: .12em; }
.story-copy h1 { margin: 0; font-family: "Songti SC", "STSong", serif; font-size: clamp(48px, 5.7vw, 82px); font-weight: 700; letter-spacing: -.07em; line-height: 1.08; }
.story-copy h1 em { color: var(--blue); font-style: normal; }
.story-note { max-width: 540px; margin: 30px 0 0; color: #5f718f; font-size: 16px; line-height: 1.85; }
.timeline-signature { position: relative; z-index: 1; max-width: 680px; }
.time-code { color: #7c8ba4; font-family: "SFMono-Regular", Consolas, monospace; font-size: 11px; }
.timeline-track { position: relative; height: 3px; margin-top: 12px; background: rgba(53,111,241,.16); }
.timeline-track i { display: block; width: 42%; height: 100%; background: var(--blue); }
.timeline-track b { position: absolute; top: 50%; width: 11px; height: 11px; background: #fff; border: 3px solid var(--blue); border-radius: 50%; transform: translate(-50%, -50%); }
.timeline-track b:nth-of-type(1) { left: 18%; }.timeline-track b:nth-of-type(2) { left: 55%; }.timeline-track b:nth-of-type(3) { left: 86%; }
.timeline-notes { display: flex; justify-content: space-between; margin-top: 12px; color: #7082a0; font-size: 11px; font-weight: 700; }
.auth-panel { display: grid; min-height: 100vh; padding: 42px; place-items: center; background: #fff; }
.auth-card { width: min(410px, 100%); }
.auth-card header { display: flex; gap: 14px; align-items: center; margin-bottom: 30px; }
.welcome-mark { display: grid; width: 44px; height: 44px; place-items: center; color: #fff; background: var(--ink); border-radius: 13px; font-family: Georgia, serif; font-size: 20px; }
.auth-card header p { margin: 0 0 3px; color: #8792a5; font-size: 12px; }.auth-card h2 { margin: 0; font-size: 25px; letter-spacing: -.04em; }
.auth-tabs { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; margin-bottom: 26px; padding: 4px; background: #f1f4f9; border-radius: 10px; }
.auth-tabs button { min-height: 38px; color: #7f8b9e; background: transparent; border: 0; border-radius: 7px; font-size: 13px; font-weight: 700; }
.auth-tabs button.active { color: #254fba; background: #fff; box-shadow: 0 3px 11px rgba(33,52,91,.08); }
form { display: grid; gap: 17px; } form label > span { display: block; margin-bottom: 8px; color: #46546b; font-size: 12px; font-weight: 700; }
form input { width: 100%; height: 49px; padding: 0 14px; color: #24324a; background: #fbfcfe; border: 1px solid #dfe5ef; border-radius: 9px; outline: none; font-size: 14px; transition: border-color .16s, box-shadow .16s; }
form input:focus { border-color: #7ba0f7; box-shadow: 0 0 0 4px rgba(53,111,241,.09); } form input::placeholder { color: #aeb7c5; }
.auth-submit { min-height: 51px; margin-top: 4px; color: #fff; background: var(--blue); border: 0; border-radius: 9px; box-shadow: 0 9px 22px rgba(53,111,241,.22); font-size: 14px; font-weight: 800; }.auth-submit:hover:not(:disabled) { background: #245fdc; }.auth-submit span { margin-left: 8px; font-size: 18px; }
.auth-error { margin: -4px 0 0; color: #c84f45; font-size: 12px; line-height: 1.5; }
.register-gift { display: flex; gap: 12px; align-items: center; margin: 26px 0 0; padding: 15px; color: #54627a; background: #fff9ef; border: 1px solid #f4dfbd; border-radius: 10px; font-size: 12px; }.register-gift b { color: var(--amber); font-family: Georgia, serif; font-size: 28px; }.register-gift span { line-height: 1.45; }.register-gift small { color: #9a8769; }
@media (max-width: 860px) { .auth-page { display: block; background: #eef4ff; }.auth-story { min-height: auto; padding: 28px 24px 48px; }.story-copy { margin: 70px 0 45px; }.story-copy h1 { font-size: 50px; }.auth-panel { min-height: auto; padding: 42px 24px 60px; border-radius: 24px 24px 0 0; }.timeline-signature { display: none; } }
@media (max-width: 480px) { .auth-brand small { display: none; }.story-copy { margin-top: 55px; }.story-copy h1 { font-size: 42px; }.story-note { font-size: 14px; }.auth-panel { padding-top: 34px; } }
</style>
