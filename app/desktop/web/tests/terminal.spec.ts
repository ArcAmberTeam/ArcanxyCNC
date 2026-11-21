import { test, expect } from '@playwright/test'
import type { TerminalEvent } from '../bridge'

test('developer switch controls terminal navigation, persistence and local session lifetime', async ({ page }) => {
  const calls: string[] = []
  await page.exposeFunction('recordTerminalCall', (value: string) => calls.push(value))
  await page.addInitScript(() => {
    const record = (window as unknown as { recordTerminalCall: (value: string) => void }).recordTerminalCall
    let receive: ((event: TerminalEvent) => void) | undefined
    window.cncTerminal = {
      setEnabled: enabled => record(String(enabled)),
      async open(id) { record('open'); receive?.({ id, kind: 'data', text: 'Password: ' }) },
      input: (_id, text) => record(text), resize: () => {}, consumed: () => {},
      close: () => record('close'),
      onEvent(callback) { receive = callback; return () => { receive = undefined } },
    }
  })
  await page.goto('/')
  const previewBounds = await page.getByRole('region', { name: '预览', exact: true }).boundingBox()
  expect(previewBounds).not.toBeNull()
  const tab = page.getByRole('button', { name: '终端', exact: true })
  const settings = page.getByRole('button', { name: '设置', exact: true })
  const toggle = page.getByRole('switch', { name: '启用终端' })
  await expect(tab).toHaveCount(0)
  await settings.click()
  await toggle.click()
  await expect(tab).toBeVisible()
  expect(calls).not.toContain('open')
  await page.reload()
  await tab.click()
  const terminal = page.getByRole('region', { name: '系统终端' })
  await expect(terminal).toBeVisible()
  await expect(terminal).toHaveCSS('background-color', 'rgb(0, 0, 0)')
  expect(await terminal.boundingBox()).toEqual(previewBounds)
  await expect.poll(() => calls.includes('open')).toBe(true)
  await terminal.locator('textarea').press('Tab')
  await expect.poll(() => calls.includes('\t')).toBe(true)
  await settings.click()
  await expect.poll(() => calls.includes('close')).toBe(true)
  await toggle.click()
  await expect(tab).toHaveCount(0)
  await page.reload()
  await expect(tab).toHaveCount(0)
})
