<script setup>
import { computed } from "vue"
import { useRouter } from "vue-router"
import Icon from "./Icon.vue"
import { isEventClickable, openEvent } from "../eventNav"
import {
  dateLocale,
  describeEvent,
  eventTitle,
  eventTypeColor,
  eventTypeIcon,
  t,
} from "../strings"

const props = defineProps({
  event: { type: Object, required: true },
  /** Show student name first (class cards, visits, calendar). */
  studentFirst: { type: Boolean, default: false },
  /** Show event type label beside the student name. */
  showType: { type: Boolean, default: true },
  /** full = Sep 24, 2026; compact = 9/24 Mon; none = hide date. */
  dateFormat: {
    type: String,
    default: "full",
    validator: (v) => ["full", "compact", "none"].includes(v),
  },
})

const router = useRouter()

function normalizeEvent(raw) {
  if (!raw?.kind) return raw
  if (raw.kind === "exam") {
    return {
      id: raw.id,
      event_type: "exam",
      title: raw.name,
      occurred_at: `${raw.date}T09:00:00`,
    }
  }
  if (raw.kind === "record") {
    return {
      id: raw.id,
      event_type: raw.event_type,
      student_id: raw.student_id,
      student_name: raw.student_name,
      students: raw.student_id
        ? [{ id: raw.student_id, name: raw.student_name }]
        : [],
      payload: raw.payload,
      occurred_at: `${raw.date}T09:00:00`,
      actor: raw.actor,
    }
  }
  return raw
}

const event = computed(() => normalizeEvent(props.event))
const clickable = computed(() => isEventClickable(event.value))

function fmtDate(ts) {
  if (!ts || props.dateFormat === "none") return ""
  const d = new Date(ts)
  if (props.dateFormat === "compact") {
    return d.toLocaleDateString(dateLocale(), {
      month: "numeric",
      day: "numeric",
      weekday: "short",
    })
  }
  return d.toLocaleDateString(dateLocale(), {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}

function onClick() {
  if (clickable.value) openEvent(router, event.value)
}

// 参与人展示：整班参加的班只显示班级名，其余逐个列出；
// 班级与散个学生混排时，班级名带「（全班）」标记避免混淆
const participantItems = computed(() => {
  if (event.value.event_type !== "activity") return []
  const whole = event.value.whole_classes ?? []
  const wholeNames = new Set(whole.map((c) => c.name))
  const individuals = (event.value.students ?? []).filter(
    (s) => !(s.class_name && wholeNames.has(s.class_name))
  )
  const items = whole.map((c) => ({
    key: `c-${c.id}`,
    label: individuals.length ? `${c.name}（全班）` : c.name,
    to: `/classes/${c.id}`,
  }))
  for (const s of individuals) {
    items.push({ key: `s-${s.id}`, label: s.name, to: `/students/${s.id}` })
  }
  return items
})

const participantsLabel = computed(() => {
  const items = participantItems.value
  if (items.length && items.every((i) => i.to.startsWith("/classes/"))) {
    return t("feed.participantClasses")
  }
  return t("feed.participants")
})
</script>

<template>
  <div
    class="feed__item"
    :class="{ 'feed__item--clickable': clickable }"
    @click="onClick"
  >
    <span class="feed__dot" :style="{ background: eventTypeColor(event.event_type) }">
      <Icon :name="eventTypeIcon(event.event_type)" :size="13" />
    </span>
    <div class="feed__body">
      <div class="feed__head">
        <span>
          <!-- 活动（比赛等）：标题承载了发生的事，标题独占一行，参与人另起一行 -->
          <template v-if="event.event_type === 'activity' && !studentFirst">
            {{ event.title }}
          </template>
          <template v-else-if="studentFirst && event.student_name">
            <router-link
              v-if="event.student_id"
              :to="`/students/${event.student_id}`"
              @click.stop
            >{{ event.student_name }}</router-link>
            <template v-else>{{ event.student_name }}</template>
            <template v-if="showType">
              · {{ eventTitle(event.event_type, event.payload) }}
            </template>
          </template>
          <template v-else-if="event.event_type === 'exam'">
            <router-link :to="`/exams/${event.id}`" @click.stop>{{ event.title }}</router-link>
            <template v-if="showType">
              · {{ eventTitle(event.event_type, event.payload) }}
            </template>
          </template>
          <template v-else-if="event.students?.length === 1">
            <router-link :to="`/students/${event.students[0].id}`" @click.stop>
              {{ event.students[0].name }}
            </router-link>
            <template v-if="showType">
              · {{ eventTitle(event.event_type, event.payload) }}
            </template>
          </template>
          <template v-else>
            {{ event.title }}
            <template v-if="showType">
              · {{ eventTitle(event.event_type, event.payload) }}
            </template>
            <template v-if="event.actor"> · {{ event.actor }}</template>
          </template>
          <span
            v-if="event.event_type === 'home_visited' && event.payload?.done"
            class="pill pill--ok feed__done"
          >{{ t("visits.done") }}</span>
          <slot name="badges" />
        </span>
        <span class="row-wrap" style="gap: 8px">
          <slot name="actions" />
          <time v-if="dateFormat !== 'none' && event.occurred_at" class="timeline__time">
            {{ fmtDate(event.occurred_at) }}
          </time>
        </span>
      </div>
      <p
        v-if="event.event_type === 'activity' && !studentFirst && participantItems.length"
        class="feed__desc"
      >
        {{ participantsLabel }}
        <template v-for="(item, i) in participantItems" :key="item.key">
          <router-link v-if="item.to" :to="item.to" @click.stop>{{ item.label }}</router-link>
          <template v-else>{{ item.label }}</template>
          <template v-if="i < participantItems.length - 1">、</template>
        </template>
      </p>
      <p v-if="describeEvent(event.event_type, event.payload)" class="feed__desc">
        {{ describeEvent(event.event_type, event.payload) }}
      </p>
      <p v-else-if="event.students?.length > 1" class="feed__desc">
        <template v-for="(s, i) in event.students" :key="s.id">
          <router-link :to="`/students/${s.id}`" @click.stop>{{ s.name }}</router-link><template v-if="i < event.students.length - 1">、</template>
        </template>
      </p>
    </div>
  </div>
</template>
