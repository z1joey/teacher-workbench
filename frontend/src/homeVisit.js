import api from "./api"
import { t } from "./strings"

export function homeVisitPatchBody(payload, done = true) {
  const p = payload || {}
  return {
    event_type: "home_visited",
    purpose: p.purpose || t("event.defaultPurpose"),
    summary: p.summary || "",
    done,
  }
}

export async function markHomeVisitDone(studentId, eventId, payload) {
  await api.patch(`/students/${studentId}/events/${eventId}`, homeVisitPatchBody(payload, true))
  return { ...(payload || {}), done: true }
}

/** Normalize list/dashboard/timeline rows into { id, student_id, payload }. */
export function homeVisitRow(event) {
  if (!event || event.event_type !== "home_visited") return null
  const student_id = event.student_id || event.students?.[0]?.id
  if (!student_id || !event.id) return null
  return { id: event.id, student_id, payload: event.payload || {} }
}
