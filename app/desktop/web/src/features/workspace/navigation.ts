import { Eye, Settings, SlidersHorizontal } from '@lucide/vue'

export const workspaceSections = [
  { id: 'preview', label: '预览', icon: Eye },
  { id: 'control', label: '控制', icon: SlidersHorizontal },
  { id: 'settings', label: '设置', icon: Settings },
] as const

export type WorkspaceSection = (typeof workspaceSections)[number]['id']
