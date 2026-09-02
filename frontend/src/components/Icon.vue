<script setup>
// Dependency-free stroke icon set (24×24, stroke = currentColor), drawn for
// this app: board = the classroom chalkboard, clipboard = exams, home = visits,
// alert = weaknesses, pencil = score corrections, swap = class moves.
const PATHS = {
  board: `<rect x="3" y="4" width="18" height="12.5" rx="1.5"/><path d="M12 16.5V20"/><path d="M7.5 20h9"/><path d="M7 8.5h7"/><path d="M7 11.5h4"/>`,
  plus: `<path d="M12 5v14"/><path d="M5 12h14"/>`,
  clipboard: `<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1"/><path d="M9 12h6"/><path d="M9 16h4"/>`,
  users: `<circle cx="9" cy="8" r="3.5"/><path d="M3.5 20a5.5 5.5 0 0 1 11 0"/><path d="M16 4.8a3.5 3.5 0 0 1 0 6.4"/><path d="M17.8 15.3c1.9.8 2.7 2.6 2.7 4.7"/>`,
  home: `<path d="M4 10.5 12 4l8 6.5"/><path d="M6 9v11h12V9"/><path d="M10 20v-5.5h4V20"/>`,
  alert: `<path d="M12 3.8 2.8 19.5h18.4L12 3.8z"/><path d="M12 10v4.2"/><path d="M12 17.4v.01"/>`,
  pencil: `<path d="M4.5 19.5l.9-3.6L16.7 4.6a2 2 0 0 1 2.8 2.8L8.2 18.7l-3.7.8z"/><path d="M14.7 6.6l2.8 2.8"/>`,
  swap: `<path d="M8 3 4 7l4 4"/><path d="M4 7h16"/><path d="M16 21l4-4-4-4"/><path d="M20 17H4"/>`,
  note: `<path d="M4 6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v8l-6 6H6a2 2 0 0 1-2-2V6z"/><path d="M14 20v-4a2 2 0 0 1 2-2h4"/>`,
  enroll: `<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><path d="M10 17l5-5-5-5"/><path d="M15 12H3"/>`,
  check: `<path d="M20 6 9 17l-5-5"/>`,
  "chevron-left": `<path d="M14.5 5.5 8 12l6.5 6.5"/>`,
  "chevron-up": `<path d="m5.5 14.5 6.5-6.5 6.5 6.5"/>`,
  "chevron-down": `<path d="m5.5 9.5 6.5 6.5 6.5-6.5"/>`,
}

defineProps({
  name: { type: String, required: true },
  size: { type: Number, default: 16 },
})
</script>

<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    class="icon"
    v-html="PATHS[name] || ''"
  />
</template>
