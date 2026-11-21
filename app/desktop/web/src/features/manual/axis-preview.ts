// Browser development reads and saves the three local preview INIs through Vite.
import type { AxisParameterDocument, AxisParameterFiles } from '../../../bridge'

declare const __AXIS_PREVIEW_FILES__: boolean
async function request(body: object): Promise<AxisParameterDocument> {
  const response = await fetch('/__axis-presets', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  const result = await response.json()
  if (!response.ok || result.error || !result.revision || !result.values) throw new Error(result.error || '无法读写本机预置 INI')
  return result
}

export const previewFiles: AxisParameterFiles | undefined = import.meta.env.DEV ? {
  read: count => request({ operation: 'read', count }),
  save: __AXIS_PREVIEW_FILES__ ? (count, revision, changes) => request({ operation: 'save', count, revision, changes }) : undefined,
} : undefined
