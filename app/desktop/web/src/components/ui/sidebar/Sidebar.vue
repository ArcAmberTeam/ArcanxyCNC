<script setup lang="ts">
import type { SidebarProps } from "."
import { cn } from "@/components/ui/classes"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { SIDEBAR_WIDTH_MOBILE, useSidebar } from "./utils"

defineOptions({
  inheritAttrs: false,
})

const props = withDefaults(defineProps<SidebarProps>(), {
  side: "left",
  variant: "sidebar",
  collapsible: "offcanvas",
})

const { isMobile, state, openMobile, setOpenMobile } = useSidebar()
</script>

<template>
  <div
    v-if="collapsible === 'none'"
    data-slot="sidebar"
    :data-variant="variant"
    :data-side="side"
    :class="cn(
      'sidebar-static text-sidebar-foreground flex w-(--sidebar-width) shrink-0 flex-col',
      variant === 'floating' ? 'sidebar-glass' : 'bg-sidebar',
      props.class,
    )"
    v-bind="$attrs"
  >
    <slot />
  </div>

  <Sheet v-else-if="isMobile" :open="openMobile" v-bind="$attrs" @update:open="setOpenMobile">
    <SheetContent
      data-sidebar="sidebar"
      data-slot="sidebar"
      data-mobile="true"
      :side="side"
      :class="cn(
        'text-sidebar-foreground w-(--sidebar-width) p-0 [&>button]:hidden',
        variant === 'floating' ? 'sidebar-glass' : 'bg-sidebar',
      )"
      :style="{
        '--sidebar-width': SIDEBAR_WIDTH_MOBILE,
      }"
    >
      <SheetHeader class="sr-only">
        <SheetTitle>Sidebar</SheetTitle>
        <SheetDescription>Displays the mobile sidebar.</SheetDescription>
      </SheetHeader>
      <div class="flex h-full w-full flex-col">
        <slot />
      </div>
    </SheetContent>
  </Sheet>

  <div
    v-else
    class="group peer text-sidebar-foreground hidden md:block"
    data-slot="sidebar"
    :data-state="state"
    :data-collapsible="state === 'collapsed' ? collapsible : ''"
    :data-variant="variant"
    :data-side="side"
  >
    <!-- This is what handles the sidebar gap on desktop  -->
    <div
      :class="cn(
        'relative w-(--sidebar-width) bg-transparent transition-[width] duration-200 ease-linear',
        'group-data-[collapsible=offcanvas]:w-0',
        'group-data-[side=right]:rotate-180',
        variant === 'floating' || variant === 'inset'
          ? 'group-data-[collapsible=icon]:w-[calc(var(--sidebar-width-icon)+(--spacing(4)))]'
          : 'group-data-[collapsible=icon]:w-(--sidebar-width-icon)',
      )"
    />
    <div
      :class="cn(
        'fixed inset-y-0 z-10 hidden h-svh w-(--sidebar-width) transition-[left,right,width] duration-200 ease-linear md:flex',
        side === 'left'
          ? 'left-0 group-data-[collapsible=offcanvas]:left-[calc(var(--sidebar-width)*-1)]'
          : 'right-0 group-data-[collapsible=offcanvas]:right-[calc(var(--sidebar-width)*-1)]',
        // Adjust the padding for floating and inset variants.
        variant === 'floating' || variant === 'inset'
          ? 'p-2 group-data-[collapsible=icon]:w-[calc(var(--sidebar-width-icon)+(--spacing(4))+2px)]'
          : 'group-data-[collapsible=icon]:w-(--sidebar-width-icon) group-data-[side=left]:border-r group-data-[side=right]:border-l',
        props.class,
      )"
      v-bind="$attrs"
    >
      <div
        data-sidebar="sidebar"
        :class="cn(
          'flex h-full w-full flex-col',
          variant === 'floating' ? 'sidebar-glass' : 'bg-sidebar',
        )"
      >
        <slot />
      </div>
    </div>
  </div>
</template>

<style scoped>
/* BEGIN: FloatingGlassSurface */
.sidebar-static[data-variant="floating"] {
  position: sticky;
  top: var(--sidebar-floating-gap);
  height: calc(100svh - 2 * var(--sidebar-floating-gap));
  margin: var(--sidebar-floating-gap);
}

.sidebar-glass {
  position: relative;
  isolation: isolate;
  border: 1px solid rgb(122 136 156 / 10%);
  border-radius: var(--sidebar-glass-radius);
  background:
    radial-gradient(ellipse at 50% 48%, rgb(148 164 185 / 16%) 0%, rgb(180 193 209 / 7%) 45%, transparent 78%),
    linear-gradient(145deg, rgb(255 255 255 / 76%), rgb(249 251 255 / 42%) 52%, rgb(255 255 255 / 62%));
  -webkit-backdrop-filter: blur(24px) saturate(145%);
  backdrop-filter: blur(24px) saturate(145%);
  box-shadow:
    0 22px 48px -22px rgb(40 57 80 / 22%),
    0 6px 18px -10px rgb(40 57 80 / 16%),
    inset 0 0 24px rgb(255 255 255 / 72%);
}

.sidebar-glass::before,
.sidebar-glass::after {
  content: "";
  position: absolute;
  inset: 0;
  z-index: -1;
  border-radius: inherit;
  pointer-events: none;
}

/* The broad center tint fades toward a thin, illuminated perimeter. */
.sidebar-glass::before {
  background:
    linear-gradient(115deg, rgb(255 255 255 / 80%), transparent 24% 76%, rgb(255 255 255 / 48%)),
    radial-gradient(ellipse at 50% 0%, rgb(255 255 255 / 85%), transparent 62%);
  box-shadow:
    inset 1px 1px 0 rgb(255 255 255 / 95%),
    inset -1px -1px 0 rgb(255 255 255 / 65%);
}

.sidebar-glass::after {
  inset: 1px;
  border-radius: calc(var(--sidebar-glass-radius) - 1px);
  box-shadow:
    inset 0 8px 12px -12px rgb(255 255 255 / 90%),
    inset 0 -8px 12px -12px rgb(85 108 140 / 18%);
}

@media (prefers-reduced-transparency: reduce) {
  .sidebar-glass {
    background: var(--sidebar);
    -webkit-backdrop-filter: none;
    backdrop-filter: none;
  }
}
/* END: FloatingGlassSurface */
</style>
