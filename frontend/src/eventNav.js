/** Resolve a detail/edit route for a timeline or feed event row. */

const SYSTEM_TYPES = new Set([
  "birthday",
  "enrolled",
  "class_moved",
  "exam_taken",
  "result_changed",
])

export function eventStudentId(e) {
  if (e.student_id) return e.student_id
  if (e.payload?.about?.id) return e.payload.about.id
  if (e.students?.length === 1) return e.students[0].id
  return null
}

export function eventRoute(e) {
  const id = e?.id
  if (!id || e?.event_type === "birthday") return null
  const type = e.event_type
  if (type === "exam") return `/exams/${id}`
  if (type === "comment") return `/comments/${id}`
  // 总结：复用学生总结页（历史列表），定位到这条
  if (type === "summary") {
    const sid = eventStudentId(e)
    if (sid) return { path: `/students/${sid}/summaries`, query: { focus: id } }
  }
  const sid = eventStudentId(e)
  if (sid) return `/students/${sid}/events/${id}`
  return null
}

export function isEventClickable(e) {
  return eventRoute(e) != null
}

export function isEventEditable(e) {
  if (e?.is_system === true || SYSTEM_TYPES.has(e?.event_type)) return false
  return isEventClickable(e)
}

export function openEvent(router, e) {
  const to = eventRoute(e)
  if (to) router.push(to)
}
