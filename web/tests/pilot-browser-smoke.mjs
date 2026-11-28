import assert from 'node:assert/strict'
import { chromium } from 'playwright'

const baseUrl = process.env.INCIDENT_ATLAS_WEB_URL ?? 'http://127.0.0.1:5173'
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || undefined,
})

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto(`${baseUrl.replace(/\/$/, '')}/pilot?workspace=payments-team`)
  await page.getByRole('heading', { name: 'Sign in to continue' }).waitFor()
  await page.getByLabel('Local seeded identity').selectOption('pilot.payments.editor')
  await page.getByRole('button', { name: 'Open local exercise workspace' }).click()
  await page.getByRole('heading', { name: 'Evidence handoff' }).waitFor()
  await page.getByRole('heading', { name: 'Checkout latency regression after deploy' }).waitFor()
  await page.getByText('synthetic GitHub event').waitFor()
  await page.getByText('ingested metric').waitFor()
  await page.getByText('ingested log').waitFor()
  await page.getByText('ingested trace').waitFor()

  await page.getByRole('button', { name: 'Open investigation' }).click()
  await page.getByRole('heading', { name: 'Evidence-backed hypothesis' }).waitFor()
  await page.getByText('FRESH ANALYSIS').waitFor()
  const citedEvidence = page.locator('.pilot-citations .pilot-citation').first()
  const evidenceId = await citedEvidence.innerText()
  await citedEvidence.click()
  await page.locator('.pilot-evidence-detail').getByText(evidenceId, { exact: true }).waitFor()
  await page.getByText(/Resolved from captured snapshot/).waitFor()
  await page.getByText(/SHA-256/).last().waitFor()
  assert.deepEqual(errors, [], 'the pilot workflow should not emit browser exceptions')
  console.log('Pilot browser smoke passed: local editor sign-in, four signals, saved investigation, and snapshot citation resolution.')
} finally {
  await browser.close()
}
