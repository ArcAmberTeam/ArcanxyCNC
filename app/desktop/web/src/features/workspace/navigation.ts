import { Eye, Settings, SlidersHorizontal, Terminal } from '@lucide/vue'

export const workspaceSections = [
  { id: 'preview', label: '预览', icon: Eye },
  { id: 'control', label: '控制', icon: SlidersHorizontal },
  { id: 'settings', label: '设置', icon: Settings },
  { id: 'terminal', label: '终端', icon: Terminal },
] as const

export type WorkspaceSection = (typeof workspaceSections)[number]['id']
