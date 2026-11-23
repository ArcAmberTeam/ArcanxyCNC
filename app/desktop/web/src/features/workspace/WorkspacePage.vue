<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { SidebarProvider } from '@/components/ui/sidebar'
import WorkspaceSidebar from './WorkspaceSidebar.vue'
import { workspaceSections, type WorkspaceSection } from './navigation'

const activeSection = ref<WorkspaceSection>('preview')
const props = defineProps<{ canEstop: boolean; estop: boolean | null; startDisabled: boolean; terminalEnabled: boolean }>()
const emit = defineEmits<{ startCycle: []; setEmergencyStop: [enabled: boolean]; sectionChange: [] }>()
watch(() => props.terminalEnabled, enabled => {
  if (!enabled && activeSection.value === 'terminal') activeSection.value = 'settings'
})
watch(activeSection, () => emit('sectionChange'))
const sectionLabel = computed(() => workspaceSections.find(section => section.id === activeSection.value)?.label)
</script>

<template>
  <SidebarProvider :open="true" :keyboard-shortcut="false" style="--sidebar-width: 8rem">
    <WorkspaceSidebar v-model="activeSection" :terminal-enabled="terminalEnabled" :can-estop="canEstop" :estop="estop" :start-disabled="startDisabled"
      @start-cycle="emit('startCycle')" @set-emergency-stop="emit('setEmergencyStop', $event)" />
    <main
      id="workspace-main"
      :aria-label="sectionLabel"
      :data-section="activeSection"
      class="min-h-svh min-w-0 flex-1 bg-background"
    >
      <slot :active-section="activeSection" />
    </main>
  </SidebarProvider>
</template>
