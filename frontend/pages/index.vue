<!-- frontend/pages/index.vue -->
<template>
  <div>
    <Dashboard />
  </div>
</template>

<script setup lang="ts">
// This page component now imports and displays the main Dashboard component
// as the default page for the application.
import Dashboard from '~/components/Dashboard.vue';
</script>