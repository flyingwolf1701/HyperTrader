<template>
  <div class="bg-gray-900 text-gray-100 min-h-screen font-sans">
    <header class="p-4 border-b border-gray-700 flex justify-between items-center">
      <h1 class="text-2xl font-bold text-green-400">HyperTrader</h1>
      <nav class="flex space-x-4">
        <NuxtLink to="/" class="text-gray-300 hover:text-green-400">Dashboard</NuxtLink>
        <NuxtLink to="/pairs" class="text-gray-300 hover:text-green-400">Manage Pairs</NuxtLink>
        <NuxtLink to="/trade/new" class="text-gray-300 hover:text-green-400">New Trade</NuxtLink>
      </nav>
    </header>
    <main class="p-4">
      <!-- NuxtPage will render the current page based on the route -->
      <NuxtPage />
    </main>
  </div>
</template>

<style>
/* Basic global styles */
body {
  margin: 0;
  font-family: 'Inter', sans-serif;
}
.router-link-active {
  color: #4ade80; /* text-green-400 */
}
</style>