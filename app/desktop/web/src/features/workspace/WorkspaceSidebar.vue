<script setup lang="ts">
import { computed } from 'vue'
import { OctagonX, Play } from '@lucide/vue'
import { Button } from '@/components/ui/button'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar'
import { workspaceSections, type WorkspaceSection } from './navigation'

const activeSection = defineModel<WorkspaceSection>({ required: true })
const props = defineProps<{ canEstop: boolean; estop: boolean | null; resetPending: boolean; startDisabled: boolean; terminalEnabled: boolean }>()
const visibleSections = computed(() => workspaceSections.filter(section => section.id !== 'terminal' || props.terminalEnabled))
const waitingForReset = computed(() => props.estop === true && props.resetPending)
const estopLabel = computed(() => {
  if (waitingForReset.value) return '等待复位'
  return props.estop === true ? '解除急停' : '急停'
})
const emit = defineEmits<{ startCycle: []; setEmergencyStop: [enabled: boolean] }>()
</script>

<template>
  <Sidebar
    side="left"
    variant="floating"
    collapsible="none"
    role="complementary"
    aria-label="侧边栏"
  >
    <SidebarContent class="px-3 pt-4">
      <nav aria-label="主导航">
        <SidebarMenu class="gap-1.5">
          <SidebarMenuItem v-for="section in visibleSections" :key="section.id">
            <SidebarMenuButton
              type="button"
              variant="workspace"
              :aria-label="section.label"
              :title="section.label"
              :is-active="activeSection === section.id"
              :aria-current="activeSection === section.id ? 'page' : undefined"
              aria-controls="workspace-main"
              class="h-11 justify-start gap-1.5 p-0 pl-6"
              @click="activeSection = section.id"
            >
              <component :is="section.icon" :stroke-width="1.75" aria-hidden="true" />
              <span class="text-xs leading-none">{{ section.label }}</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </nav>
    </SidebarContent>
    <SidebarFooter class="px-3 pb-4 pt-3">
      <Button type="button" :disabled="startDisabled" title="启动机床，回零后运行当前程序"
        class="h-11 w-full gap-1.5 rounded-2xl p-0" @click="emit('startCycle')">
        <Play class="size-5" :stroke-width="1.75" aria-hidden="true" />
        <span class="text-xs leading-none">启动</span>
      </Button>
      <div :title="canEstop ? estopLabel : '控制服务未就绪'">
        <Button
          :key="estopLabel"
          type="button"
          variant="destructive"
          :disabled="!canEstop || waitingForReset"
          class="h-11 w-full gap-1.5 rounded-2xl p-0 disabled:opacity-60"
          @click="emit('setEmergencyStop', estop !== true)"
        >
          <OctagonX class="size-5" :stroke-width="1.75" aria-hidden="true" />
          <span class="text-xs leading-none">{{ estopLabel }}</span>
        </Button>
      </div>
    </SidebarFooter>
  </Sidebar>
</template>
