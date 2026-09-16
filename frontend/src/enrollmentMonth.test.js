import test from "node:test"
import assert from "node:assert/strict"
import {
  buildEnrollmentMonth,
  formatEnrollmentMonth,
  parseEnrollmentMonth,
} from "./strings.js"

test("parseEnrollmentMonth accepts canonical YYYY-MM", () => {
  assert.deepEqual(parseEnrollmentMonth("2025-09"), { year: 2025, month: 9 })
})

test("parseEnrollmentMonth rejects invalid values", () => {
  assert.equal(parseEnrollmentMonth(""), null)
  assert.equal(parseEnrollmentMonth("2025/09"), null)
  assert.equal(parseEnrollmentMonth("2025-13"), null)
  assert.equal(parseEnrollmentMonth("1899-09"), null)
})

test("buildEnrollmentMonth pads month", () => {
  assert.equal(buildEnrollmentMonth(2025, 9), "2025-09")
  assert.equal(buildEnrollmentMonth(2025, 12), "2025-12")
})

test("formatEnrollmentMonth renders Chinese label", () => {
  assert.equal(formatEnrollmentMonth("2026-10"), "2026年10月")
})
