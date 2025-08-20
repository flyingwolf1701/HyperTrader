<template>
  <div class="max-w-4xl mx-auto">
    <h2 class="text-xl font-semibold mb-4">Manage Trading Pairs</h2>
    <div v-if="loading" class="text-gray-400">Loading pairs...</div>
    <div v-else class="bg-gray-800 rounded-lg p-4">
      <!-- In a real app, you would group these by L1 -->
      <ul class="space-y-2">
        <li v-for="pair in pairs" :key="pair" class="flex justify-between items-center p-2 rounded hover:bg-gray-700">
          <span class="font-mono">{{ pair }}</span>
          <button @click="toggleFavorite(pair)" class="text-2xl" :class="isFavorite(pair) ? 'text-yellow-400' : 'text-gray-500'">
            ★
          </button>
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';

const pairs = ref<string[]>([]);
const favorites = ref<string[]>([]);
const loading = ref(true);

// Fetch all available pairs and current favorites from the backend
onMounted(async () => {
  try {
    // Replace with your actual API URL
    const [pairsRes, favsRes] = await Promise.all([
      fetch('http://localhost:8000/api/v1/exchange/pairs'),
      fetch('http://localhost:8000/api/v1/user/favorites') // Assuming this endpoint exists
    ]);
    const pairsData = await pairsRes.json();
    const favsData = await favsRes.json();
    
    pairs.value = pairsData.pairs || [];
    favorites.value = favsData.favorites || [];

  } catch (error) {
    console.error("Failed to fetch pairs data:", error);
  } finally {
    loading.value = false;
  }
});

const isFavorite = (pair: string) => favorites.value.includes(pair);

const toggleFavorite = async (pair: string) => {
  const isFav = isFavorite(pair);
  // In a real app, you'd POST to the backend to update the favorite status
  // and then update the local state on success.
  if (isFav) {
    favorites.value = favorites.value.filter(p => p !== pair);
  } else {
    favorites.value.push(pair);
  }
  console.log(`Toggled favorite for ${pair}. New list:`, favorites.value);
};
</script>