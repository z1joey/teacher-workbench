/**
 * After POST /data/demo/seed fails client-side (timeout, 502/504, network),
 * confirm whether seed actually committed by checking workspace status.
 */
export async function recoverDemoSeedIfPresent(getStatus, onRecovered) {
  try {
    const status = await getStatus()
    if (status?.has_business_data) {
      await onRecovered()
      return true
    }
  } catch {
    // status probe failed — cannot confirm success
  }
  return false
}
