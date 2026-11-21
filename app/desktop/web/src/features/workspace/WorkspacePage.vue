<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { SidebarProvider } from '@/components/ui/sidebar'
import WorkspaceSidebar from './WorkspaceSidebar.vue'
import { workspaceSections, type WorkspaceSection } from './navigation'

const activeSection = ref<WorkspaceSection>('preview')
defineProps<{ canEstop: boolean; startDisabled: boolean }>()
const emit = defineEmits<{ startCycle: []; emergencyStop: []; sectionChange: [] }>()
watch(activeSection, () => emit('sectionChange'))
const sectionLabel = computed(() => workspaceSections.find(section => section.id === activeSection.value)?.label)
</script>

<template>
  <SidebarProvider :open="true" :keyboard-shortcut="false" style="--sidebar-width: 8rem">
    <WorkspaceSidebar v-model="activeSection" :can-estop="canEstop" :start-disabled="startDisabled" @start-cycle="emit('startCycle')" @emergency-stop="emit('emergencyStop')" />
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
