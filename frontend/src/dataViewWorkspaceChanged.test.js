import test from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const viewsDir = join(dirname(fileURLToPath(import.meta.url)), "views")

test("DataView emits workspace-changed after demo seed and reset", () => {
  const src = readFileSync(join(viewsDir, "DataView.vue"), "utf8")
  assert.match(src, /defineEmits\(\["workspace-changed"\]\)/)
  assert.match(src, /emit\("workspace-changed"\)/)
})

test("ProfileView reloads profile when workspace changes", () => {
  const src = readFileSync(join(viewsDir, "ProfileView.vue"), "utf8")
  assert.match(src, /<DataView @workspace-changed="load"/)
})
