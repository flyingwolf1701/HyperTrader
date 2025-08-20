<template>
  <div class="max-w-md mx-auto">
    <h2 class="text-xl font-semibold mb-4">Start New Trade</h2>
    <form @submit.prevent="startTrade" class="bg-gray-800 p-6 rounded-lg space-y-4">
      <div>
        <label for="symbol" class="block text-sm font-medium text-gray-300">Symbol</label>
        <select id="symbol" v-model="form.symbol" class="mt-1 block w-full bg-gray-700 border-gray-600 rounded-md shadow-sm p-2 focus:ring-green-500 focus:border-green-500">
          <option disabled value="">Select a favorite pair</option>
          <option v-for="fav in favorites" :key="fav" :value="fav">{{ fav }}</option>
        </select>
      </div>
      <div>
        <label for="margin" class="block text-sm font-medium text-gray-300">Margin ($)</label>
        <input type="number" id="margin" v-model.number="form.margin" class="mt-1 block w-full bg-gray-700 border-gray-600 rounded-md shadow-sm p-2 focus:ring-green-500 focus:border-green-500" placeholder="e.g., 100">
      </div>
      <div>
        <label for="leverage" class="block text-sm font-medium text-gray-300">Leverage</label>
        <input type="number" id="leverage" v-model.number="form.leverage" class="mt-1 block w-full bg-gray-700 border-gray-600 rounded-md shadow-sm p-2 focus:ring-green-500 focus:border-green-500" placeholder="e.g., 10">
      </div>
      <button type="submit" class="w-full bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-4 rounded">
        Initiate Trade
      </button>
    </form>
    <div v-if="message" class="mt-4 p-3 rounded" :class="isError ? 'bg-red-900 text-red-200' : 'bg-green-900 text-green-200'">
      {{ message }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';

const favorites = ref<string[]>([]);
const form = reactive({
  symbol: '',
  margin: 100,
  leverage: 10,
});
const message = ref('');
const isError = ref(false);

onMounted(async () => {
  try {
    const res = await fetch('http://localhost:8000/api/v1/user/favorites');
    const data = await res.json();
    favorites.value = data.favorites || [];
    if (favorites.value.length > 0) {
      form.symbol = favorites.value[0];
    }
  } catch (error) {
    console.error("Failed to fetch favorites:", error);
  }
});

const startTrade = async () => {
  message.value = 'Initiating trade...';
  isError.value = false;
  try {
    const response = await fetch('http://localhost:8000/api/v1/trade/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || 'Failed to start trade.');
    }
    message.value = data.message;
  } catch (error: any) {
    message.value = error.message;
    isError.value = true;
  }
};
</script>