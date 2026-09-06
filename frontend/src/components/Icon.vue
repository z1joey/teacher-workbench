<script setup>
// Dependency-free stroke icon set (24×24, stroke = currentColor).
// Drawn for this app: board = the classroom chalkboard, clipboard = exams,
// home = visits, alert = problems, pencil = score corrections, swap = class moves.
// Navigation, status and action icons were added for the shell redesign.
const PATHS = {
  /* --- 领域图标 --- */
  board: `<rect x="3" y="4" width="18" height="12.5" rx="1.5"/><path d="M12 16.5V20"/><path d="M7.5 20h9"/><path d="M7 8.5h7"/><path d="M7 11.5h4"/>`,
  clipboard: `<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1"/><path d="M9 12h6"/><path d="M9 16h4"/>`,
  home: `<path d="M4 10.5 12 4l8 6.5"/><path d="M6 9v11h12V9"/><path d="M10 20v-5.5h4V20"/>`,
  alert: `<path d="M12 3.8 2.8 19.5h18.4L12 3.8z"/><path d="M12 10v4.2"/><path d="M12 17.4v.01"/>`,
  pencil: `<path d="M4.5 19.5l.9-3.6L16.7 4.6a2 2 0 0 1 2.8 2.8L8.2 18.7l-3.7.8z"/><path d="M14.7 6.6l2.8 2.8"/>`,
  swap: `<path d="M8 3 4 7l4 4"/><path d="M4 7h16"/><path d="M16 21l4-4-4-4"/><path d="M20 17H4"/>`,
  note: `<path d="M4 6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v8l-6 6H6a2 2 0 0 1-2-2V6z"/><path d="M14 20v-4a2 2 0 0 1 2-2h4"/>`,
  enroll: `<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><path d="M10 17l5-5-5-5"/><path d="M15 12H3"/>`,
  cake: `<path d="M4 20h16"/><path d="M5 20v-5h14v5"/><path d="M7 15v-3a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v3"/><path d="M12 10V7"/><path d="M10.5 5.5c0-.8 1.5-1 1.5-2"/>`,
  "map-pin": `<path d="M20 10.5c0 5.5-8 11.5-8 11.5s-8-6-8-11.5a8 8 0 0 1 16 0z"/><circle cx="12" cy="10.5" r="3"/>`,
  flag: `<path d="M5 21V4"/><path d="M5 4c4.5-2 8.5 2 14 0v9c-5.5 2-9.5-2-14 0"/>`,

  /* --- 导航 --- */
  users: `<circle cx="9" cy="8" r="3.5"/><path d="M3.5 20a5.5 5.5 0 0 1 11 0"/><path d="M16 4.8a3.5 3.5 0 0 1 0 6.4"/><path d="M17.8 15.3c1.9.8 2.7 2.6 2.7 4.7"/>`,
  building: `<path d="M3 21h18"/><rect x="5" y="3" width="14" height="18" rx="1.5"/><path d="M9 7h2"/><path d="M13 7h2"/><path d="M9 11h2"/><path d="M13 11h2"/><path d="M10 21v-4h4v4"/>`,
  checklist: `<path d="M11 6h9"/><path d="M11 12h9"/><path d="M11 18h9"/><path d="m3.5 6.5 1.6 1.6L8.6 4.6"/><path d="m3.5 18.5 1.6 1.6L8.6 16.6"/><path d="M3 12h3"/>`,
  user: `<circle cx="12" cy="8" r="3.6"/><path d="M4.5 20.5a7.5 7.5 0 0 1 15 0"/>`,
  sliders: `<path d="M4 7h9"/><path d="M17 7h3"/><circle cx="15" cy="7" r="2"/><path d="M4 17h3"/><path d="M11 17h9"/><circle cx="9" cy="17" r="2"/>`,
  calendar: `<rect x="3.5" y="5" width="17" height="16" rx="2"/><path d="M3.5 10h17"/><path d="M8 3v4"/><path d="M16 3v4"/>`,
  chart: `<path d="M4 20h16"/><path d="M7.5 20v-6"/><path d="M12 20V7"/><path d="M16.5 20v-9"/>`,
  trending: `<path d="m3.5 16.5 5-5 3.5 3.5L20 7.5"/><path d="M15 7.5h5v5"/>`,
  clock: `<circle cx="12" cy="12" r="9"/><path d="M12 7.5V12l3 1.8"/>`,
  tag: `<path d="M3.6 11.3V4.6a1 1 0 0 1 1-1h6.7a1 1 0 0 1 .7.3l8 8a1 1 0 0 1 0 1.4l-6.7 6.7a1 1 0 0 1-1.4 0l-8-8a1 1 0 0 1-.3-.7z"/><circle cx="7.7" cy="7.7" r="1.3"/>`,
  phone: `<path d="M6.5 3.5h3l1.5 4-2 1.5a11 11 0 0 0 5 5l1.5-2 4 1.5v3a2 2 0 0 1-2.2 2A16.5 16.5 0 0 1 4.5 5.7a2 2 0 0 1 2-2.2z"/>`,
  keyboard: `<rect x="2.5" y="6" width="19" height="12" rx="2"/><path d="M6 9.5h.01"/><path d="M9.5 9.5h.01"/><path d="M13 9.5h.01"/><path d="M16.5 9.5h.01"/><path d="M7.5 14.5h9"/>`,

  /* --- 操作 --- */
  plus: `<path d="M12 5v14"/><path d="M5 12h14"/>`,
  "plus-circle": `<circle cx="12" cy="12" r="9"/><path d="M12 8.5v7"/><path d="M8.5 12h7"/>`,
  search: `<circle cx="11" cy="11" r="7"/><path d="m21 21-4-4"/>`,
  menu: `<path d="M4 7h16"/><path d="M4 12h16"/><path d="M4 17h16"/>`,
  dots: `<circle cx="6" cy="12" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="18" cy="12" r="1.4"/>`,
  close: `<path d="M6 6l12 12"/><path d="M18 6 6 18"/>`,
  x: `<path d="M6 6l12 12"/><path d="M18 6 6 18"/>`,
  check: `<path d="M20 6 9 17l-5-5"/>`,
  "check-circle": `<circle cx="12" cy="12" r="9"/><path d="m8.4 12.2 2.4 2.4 4.8-5"/>`,
  trash: `<path d="M4 7h16"/><path d="M9.5 7V4.8h5V7"/><path d="M6.6 7l.9 12.2A1.8 1.8 0 0 0 9.3 21h5.4a1.8 1.8 0 0 0 1.8-1.8L17.4 7"/><path d="M10.5 11v6"/><path d="M13.5 11v6"/>`,
  undo: `<path d="M4 8h9.5A5.5 5.5 0 0 1 13.5 19H8"/><path d="m7.5 4.5-4 3.5 4 3.5"/>`,
  refresh: `<path d="M3.6 12a8.4 8.4 0 0 1 14.5-5.9"/><path d="M20.4 4.2v5h-5"/><path d="M20.4 12a8.4 8.4 0 0 1-14.5 5.9"/><path d="M3.6 19.8v-5h5"/>`,
  filter: `<path d="M4 6h16"/><path d="M7 12h10"/><path d="M10 18h4"/>`,
  external: `<path d="M14 4h6v6"/><path d="M20 4l-8.5 8.5"/><path d="M18 14v4.5A1.5 1.5 0 0 1 16.5 20h-11A1.5 1.5 0 0 1 4 18.5v-11A1.5 1.5 0 0 1 5.5 6H10"/>`,
  logout: `<path d="M14 4h3.5A1.5 1.5 0 0 1 19 5.5v13a1.5 1.5 0 0 1-1.5 1.5H14"/><path d="M10 17l-5-5 5-5"/><path d="M5 12h10"/>`,
  eye: `<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>`,
  "eye-off": `<path d="M9.9 5.7A8.9 8.9 0 0 1 12 5.5c6 0 9.5 6.5 9.5 6.5a17 17 0 0 1-2.5 3.4"/><path d="M6.2 7.7A16.6 16.6 0 0 0 2.5 12S6 18.5 12 18.5c1.6 0 3-.4 4.2-1.1"/><path d="M10 10a2.8 2.8 0 0 0 4 4"/><path d="M4 4l16 16"/>`,

  /* --- 状态 --- */
  help: `<circle cx="12" cy="12" r="9"/><path d="M9.6 9.3a2.5 2.5 0 1 1 3.6 2.3c-.8.4-1.2 1-1.2 1.9v.3"/><path d="M12 17.2v.01"/>`,
  info: `<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5"/><path d="M12 7.8v.01"/>`,
  "alert-circle": `<circle cx="12" cy="12" r="9"/><path d="M12 7.5v5"/><path d="M12 16.2v.01"/>`,
  "x-circle": `<circle cx="12" cy="12" r="9"/><path d="m9 9 6 6"/><path d="m15 9-6 6"/>`,

  /* --- 方向 --- */
  "chevron-left": `<path d="M14.5 5.5 8 12l6.5 6.5"/>`,
  "chevron-right": `<path d="m9.5 5.5 6.5 6.5-6.5 6.5"/>`,
  "chevron-up": `<path d="m5.5 14.5 6.5-6.5 6.5 6.5"/>`,
  "chevron-down": `<path d="m5.5 9.5 6.5 6.5 6.5-6.5"/>`,
  "arrow-left": `<path d="M20 12H5"/><path d="m10.5 6.5-6 5.5 6 5.5"/>`,
  "arrow-right": `<path d="M4 12h15"/><path d="m13.5 6.5 6 5.5-6 5.5"/>`,
}

const FALLBACK = `<circle cx="12" cy="12" r="8"/>`

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
    focusable="false"
    class="icon"
    v-html="PATHS[name] || FALLBACK"
  />
</template>
