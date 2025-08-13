<template>
  <div class="create-plan">
    <h1>Create Trading Plan</h1>
    <div class="plan-form">
      <form @submit.prevent="createPlan">
        <div class="form-group">
          <label for="symbol">Trading Symbol</label>
          <input type="text" id="symbol" v-model="planData.symbol" placeholder="e.g., BTC" />
        </div>
        
        <div class="form-group">
          <label for="allocation">Portfolio Allocation (%)</label>
          <input type="number" id="allocation" v-model="planData.allocation" min="1" max="100" />
        </div>
        
        <div class="fibonacci-settings">
          <h3>Fibonacci Settings</h3>
          <div class="form-group">
            <label for="hedge-trigger">Hedge Trigger Level (%)</label>
            <input type="number" id="hedge-trigger" v-model="planData.hedgeTrigger" value="23" />
          </div>
          
          <div class="form-group">
            <label for="scale-level-1">First Scale Level (%)</label>
            <input type="number" id="scale-level-1" v-model="planData.scaleLevel1" value="38" />
          </div>
          
          <div class="form-group">
            <label for="scale-level-2">Second Scale Level (%)</label>
            <input type="number" id="scale-level-2" v-model="planData.scaleLevel2" value="50" />
          </div>
        </div>
        
        <div class="form-actions">
          <button type="submit" class="btn btn-primary">Create Plan</button>
          <NuxtLink to="/plans" class="btn btn-secondary">Cancel</NuxtLink>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
const planData = ref({
  symbol: '',
  allocation: 10,
  hedgeTrigger: 23,
  scaleLevel1: 38,
  scaleLevel2: 50
})

const createPlan = () => {
  // Trading plan creation logic will go here
  console.log('Creating plan:', planData.value)
}
</script>

<style scoped>
.create-plan {
  padding: 2rem;
  max-width: 600px;
  margin: 0 auto;
}

.plan-form {
  background: #f8f9fa;
  padding: 2rem;
  border-radius: 8px;
}

.form-group {
  margin-bottom: 1.5rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 600;
}

.form-group input {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.fibonacci-settings {
  margin: 2rem 0;
  padding: 1.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.fibonacci-settings h3 {
  margin-bottom: 1rem;
}

.form-actions {
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
}

.btn {
  padding: 0.75rem 1.5rem;
  text-decoration: none;
  border-radius: 4px;
  border: none;
  cursor: pointer;
}

.btn-primary {
  background: #007bff;
  color: white;
}

.btn-secondary {
  background: #6c757d;
  color: white;
}
</style>