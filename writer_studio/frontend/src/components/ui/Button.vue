<template>
  <button
    class="ios-btn"
    :class="'ios-btn-' + variant"
    :disabled="disabled"
    type="button"
    @click="$emit('click')"
  >
    <slot />
  </button>
</template>

<script setup>
defineProps({
  variant: { type: String, default: 'primary' },
  disabled: { type: Boolean, default: false },
})
defineEmits(['click'])
</script>
