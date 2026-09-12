<script setup>
import { computed, useSlots } from "vue"
import { useRouter } from "vue-router"
import Icon from "./Icon.vue"
import { isEventClickable, openEvent } from "../eventNav"
import {
  dateLocale,
  describeEvent,
  eventDisplayName,
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
  /** Stacked layout: date on top, description, then tags row (home latest feed). */
  stacked: { type: Boolean, default: false },
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
      title: raw.title,
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
const displayName = computed(() => eventDisplayName(event.value))
const clickable = computed(() => isEventClickable(event.value))
const slots = useSlots()
const showDone = computed(
  () => event.value.event_type === "home_visited" && event.value.payload?.done
)
const hasTags = computed(() => showDone.value || !!slots.badges)

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
      <time
        v-if="stacked && dateFormat !== 'none' && event.occurred_at"
        class="timeline__time feed__date"
      >
        {{ fmtDate(event.occurred_at) }}
      </time>
      <div class="feed__head">
        <span class="feed__title-row">
          <span class="feed__title-text">
          <template v-if="studentFirst && event.student_name">
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
            <router-link :to="`/exams/${event.id}`" @click.stop>{{ displayName }}</router-link>
            <template v-if="showType">
              · {{ eventTitle(event.event_type, event.payload) }}
            </template>
          </template>
          <template v-else-if="event.students?.length === 1">
            <router-link :to="`/students/${event.students[0].id}`" @click.stop>
              {{ event.students[0].name }}
            </router-link>
            <template v-if="showType">
              · {{ displayName }}
            </template>
          </template>
          <template v-else>
            {{ displayName }}
            <template v-if="showType">
              · {{ eventTitle(event.event_type, event.payload) }}
            </template>
            <template v-if="event.actor"> · {{ event.actor }}</template>
          </template>
          </span>
          <span v-if="$slots.actions" class="feed__inline-actions">
            <slot name="actions" />
          </span>
          <span v-if="!stacked && showDone" class="pill pill--ok feed__done">
            {{ t("visits.done") }}
          </span>
          <template v-if="!stacked"><slot name="badges" /></template>
        </span>
        <time
          v-if="!stacked && dateFormat !== 'none' && event.occurred_at"
          class="timeline__time"
        >
          {{ fmtDate(event.occurred_at) }}
        </time>
      </div>
      <p v-if="describeEvent(event.event_type, event.payload)" class="feed__desc">
        {{ describeEvent(event.event_type, event.payload) }}
      </p>
      <p v-else-if="event.students?.length > 1" class="feed__desc">
        <template v-for="(s, i) in event.students" :key="s.id">
          <router-link :to="`/students/${s.id}`" @click.stop>{{ s.name }}</router-link><template v-if="i < event.students.length - 1">、</template>
        </template>
      </p>
      <div v-if="stacked && hasTags" class="feed__tags">
        <span v-if="showDone" class="pill pill--ok feed__done">{{ t("visits.done") }}</span>
        <slot name="badges" />
      </div>
    </div>
  </div>
</template>
