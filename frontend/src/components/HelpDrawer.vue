<script setup>
// 帮助抽屉：任何页面都能打开，默认展示当前页面的上下文提示
import { computed } from "vue"
import { useRoute } from "vue-router"
import Icon from "./Icon.vue"
import {
  GLOSSARY,
  PAGE_HELP,
  RULES,
  SHORTCUTS,
  START_STEPS,
  closeHelp,
} from "../help"

const route = useRoute()

const pageHelp = computed(() => PAGE_HELP[route.name] || null)
const isMac = computed(() =>
  typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform || "")
)

function keysFor(s) {
  return s.alt && !isMac.value ? s.alt : s.keys
}
</script>

<template>
  <div class="scrim" style="z-index: 114" @click="closeHelp" />
  <aside class="drawer" role="dialog" aria-modal="true" aria-labelledby="help-title">
    <header class="drawer__head">
      <h2 id="help-title" class="drawer__title">
        <Icon name="help" :size="18" /> 帮助与快捷键
      </h2>
      <button class="icon-btn" aria-label="关闭帮助" @click="closeHelp">
        <Icon name="close" :size="16" />
      </button>
    </header>

    <div class="drawer__body">
      <section v-if="pageHelp" class="help-section">
        <h3><Icon name="info" :size="16" /> {{ pageHelp.title }}</h3>
        <ul class="help-list">
          <li v-for="(tip, i) in pageHelp.items" :key="i">
            <span class="num-badge">{{ i + 1 }}</span>
            <span>{{ tip }}</span>
          </li>
        </ul>
      </section>

      <section class="help-section">
        <h3><Icon name="check-circle" :size="16" /> 三步上手</h3>
        <ul class="help-list">
          <li v-for="(s, i) in START_STEPS" :key="i">
            <span class="num-badge">{{ i + 1 }}</span>
            <span><b>{{ s.title }}</b><br /><span class="muted">{{ s.desc }}</span></span>
          </li>
        </ul>
      </section>

      <section id="help-shortcuts" class="help-section">
        <h3><Icon name="keyboard" :size="16" /> 键盘快捷键</h3>
        <div class="keys">
          <div v-for="(s, i) in SHORTCUTS" :key="i" class="keys__row">
            <span>{{ s.label }}</span>
            <span>
              <kbd v-for="(k, j) in keysFor(s)" :key="j" class="kbd">{{ k }}</kbd>
            </span>
          </div>
        </div>
      </section>

      <section id="help-glossary" class="help-section">
        <h3><Icon name="note" :size="16" /> 术语表</h3>
        <div class="stack">
          <div v-for="g in GLOSSARY" :key="g.term">
            <b>{{ g.term }}</b>
            <p class="muted" style="font-size: 13px">{{ g.desc }}</p>
          </div>
        </div>
      </section>

      <section class="help-section">
        <h3><Icon name="alert" :size="16" /> 数据规则</h3>
        <ul class="help-list">
          <li v-for="(r, i) in RULES" :key="i">
            <span class="num-badge">!</span>
            <span>{{ r }}</span>
          </li>
        </ul>
      </section>
    </div>
  </aside>
</template>
