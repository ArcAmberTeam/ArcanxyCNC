import type { SystemInfo } from '../../bridge'

export function loadSystemInfo(): Promise<SystemInfo> {
  if (!window.cncSystem) return Promise.reject(new Error('浏览器预览无法读取本机信息，请在 Linux 桌面端查看'))
  return window.cncSystem.getInfo()
}
