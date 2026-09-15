import test from "node:test"
import assert from "node:assert/strict"
import { recoverDemoSeedIfPresent } from "./demoSeedRecovery.js"

test("recovers when demo status reports business data", async () => {
  let recovered = false
  const ok = await recoverDemoSeedIfPresent(
    async () => ({ has_business_data: true }),
    async () => {
      recovered = true
    },
  )
  assert.equal(ok, true)
  assert.equal(recovered, true)
})

test("does not recover when workspace is still empty", async () => {
  let recovered = false
  const ok = await recoverDemoSeedIfPresent(
    async () => ({ has_business_data: false }),
    async () => {
      recovered = true
    },
  )
  assert.equal(ok, false)
  assert.equal(recovered, false)
})

test("does not recover when status probe fails", async () => {
  let recovered = false
  const ok = await recoverDemoSeedIfPresent(
    async () => {
      throw new Error("Failed to fetch")
    },
    async () => {
      recovered = true
    },
  )
  assert.equal(ok, false)
  assert.equal(recovered, false)
})
