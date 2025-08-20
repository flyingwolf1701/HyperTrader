<template>
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
    <div class="flex items-center justify-between mb-6">
      <h3 class="text-lg font-semibold text-gray-900 dark:text-white">Phase Progression</h3>
      <UBadge 
        :color="currentPhaseColor" 
        variant="solid"
        size="sm"
      >
        {{ systemState?.current_phase?.toUpperCase() || 'UNKNOWN' }}
      </UBadge>
    </div>

    <!-- Phase Flow Diagram -->
    <div class="mb-6">
      <div class="flex items-center justify-between mb-4">
        <div class="text-center flex-1">
          <div 
            class="w-12 h-12 mx-auto rounded-full flex items-center justify-center mb-2 transition-all"
            :class="phaseStepClass('advance')"
          >
            <UIcon name="i-heroicons-arrow-trending-up" class="text-xl" />
          </div>
          <span class="text-xs font-medium">ADVANCE</span>
        </div>
        
        <div class="flex-1">
          <div class="h-0.5 bg-gray-300 dark:bg-gray-600"></div>
        </div>
        
        <div class="text-center flex-1">
          <div 
            class="w-12 h-12 mx-auto rounded-full flex items-center justify-center mb-2 transition-all"
            :class="phaseStepClass('retracement')"
          >
            <UIcon name="i-heroicons-arrow-path" class="text-xl" />
          </div>
          <span class="text-xs font-medium">RETRACEMENT</span>
        </div>
        
        <div class="flex-1">
          <div class="h-0.5 bg-gray-300 dark:bg-gray-600"></div>
        </div>
        
        <div class="text-center flex-1">
          <div 
            class="w-12 h-12 mx-auto rounded-full flex items-center justify-center mb-2 transition-all"
            :class="phaseStepClass('decline')"
          >
            <UIcon name="i-heroicons-arrow-trending-down" class="text-xl" />
          </div>
          <span class="text-xs font-medium">DECLINE</span>
        </div>
        
        <div class="flex-1">
          <div class="h-0.5 bg-gray-300 dark:bg-gray-600"></div>
        </div>
        
        <div class="text-center flex-1">
          <div 
            class="w-12 h-12 mx-auto rounded-full flex items-center justify-center mb-2 transition-all"
            :class="phaseStepClass('recovery')"
          >
            <UIcon name="i-heroicons-arrow-up-right" class="text-xl" />
          </div>
          <span class="text-xs font-medium">RECOVERY</span>
        </div>
      </div>
    </div>

    <!-- Current Phase Details -->
    <div v-if="systemState" class="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
      <div class="grid grid-cols-2 gap-4">
        <div>
          <p class="text-sm text-gray-600 dark:text-gray-400 mb-1">Current Unit Position</p>
          <p class="text-2xl font-bold text-gray-900 dark:text-white">
            {{ systemState.current_unit }}
          </p>
        </div>
        
        <div>
          <p class="text-sm text-gray-600 dark:text-gray-400 mb-1">Reference Points</p>
          <div class="text-sm">
            <div class="flex justify-between">
              <span class="text-gray-600 dark:text-gray-400">Peak:</span>
              <span class="font-medium text-gray-900 dark:text-white">
                {{ systemState.peak_unit || 'N/A' }}
              </span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-600 dark:text-gray-400">Valley:</span>
              <span class="font-medium text-gray-900 dark:text-white">
                {{ systemState.valley_unit || 'N/A' }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Phase Characteristics -->
    <div class="mt-6 space-y-3">
      <h4 class="text-sm font-semibold text-gray-900 dark:text-white">Phase Characteristics:</h4>
      
      <div class="text-sm space-y-2">
        <div v-if="systemState?.current_phase === 'advance'" class="flex items-start space-x-2">
          <UIcon name="i-heroicons-check-circle" class="text-green-500 text-lg mt-0.5" />
          <div>
            <p class="font-medium text-gray-900 dark:text-white">Building Positions</p>
            <p class="text-gray-600 dark:text-gray-400">Both allocations riding upward trend</p>
          </div>
        </div>
        
        <div v-if="systemState?.current_phase === 'retracement'" class="flex items-start space-x-2">
          <UIcon name="i-heroicons-exclamation-triangle" class="text-yellow-500 text-lg mt-0.5" />
          <div>
            <p class="font-medium text-gray-900 dark:text-white">Decline from Peak</p>
            <p class="text-gray-600 dark:text-gray-400">Scaling positions with confirmation rules</p>
          </div>
        </div>
        
        <div v-if="systemState?.current_phase === 'decline'" class="flex items-start space-x-2">
          <UIcon name="i-heroicons-shield-exclamation" class="text-red-500 text-lg mt-0.5" />
          <div>
            <p class="font-medium text-gray-900 dark:text-white">Full Protection Mode</p>
            <p class="text-gray-600 dark:text-gray-400">Long fully cashed, hedge fully short</p>
          </div>
        </div>
        
        <div v-if="systemState?.current_phase === 'recovery'" class="flex items-start space-x-2">
          <UIcon name="i-heroicons-arrow-up" class="text-blue-500 text-lg mt-0.5" />
          <div>
            <p class="font-medium text-gray-900 dark:text-white">Systematic Re-entry</p>
            <p class="text-gray-600 dark:text-gray-400">Recovery from valley with confirmations</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Special Conditions Display -->
    <div v-if="isResetConditionMet || isChoppyTradingActive" class="mt-6 pt-4 border-t border-gray-200 dark:border-gray-600">
      <h4 class="text-sm font-semibold text-gray-900 dark:text-white mb-3">System Status:</h4>
      
      <div class="space-y-2">
        <div v-if="isResetConditionMet" class="flex items-center space-x-2 text-sm">
          <div class="w-2 h-2 bg-blue-500 rounded-full"></div>
          <span class="text-gray-900 dark:text-white font-medium">Reset Conditions Met</span>
        </div>
        
        <div v-if="isChoppyTradingActive" class="flex items-center space-x-2 text-sm">
          <div class="w-2 h-2 bg-yellow-500 rounded-full animate-pulse"></div>
          <span class="text-gray-900 dark:text-white font-medium">Choppy Trading Active</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const { 
  systemState, 
  isResetConditionMet, 
  isChoppyTradingActive 
} = useSystemState()

// Current phase color mapping
const currentPhaseColor = computed(() => {
  if (!systemState.value) return 'gray'
  
  const phaseColors = {
    advance: 'green',
    retracement: 'yellow', 
    decline: 'red',
    recovery: 'blue'
  }
  
  return phaseColors[systemState.value.current_phase] || 'gray'
})

// Phase step styling
const phaseStepClass = (phase: string) => {
  const isCurrentPhase = systemState.value?.current_phase === phase
  
  const baseClasses = 'transition-all duration-300'
  const phaseStyles = {
    advance: 'bg-green-100 text-green-600 border-2 border-green-300',
    retracement: 'bg-yellow-100 text-yellow-600 border-2 border-yellow-300',
    decline: 'bg-red-100 text-red-600 border-2 border-red-300',
    recovery: 'bg-blue-100 text-blue-600 border-2 border-blue-300'
  }
  
  const activeStyles = {
    advance: 'bg-green-500 text-white border-green-500 shadow-lg scale-110',
    retracement: 'bg-yellow-500 text-white border-yellow-500 shadow-lg scale-110',
    decline: 'bg-red-500 text-white border-red-500 shadow-lg scale-110',
    recovery: 'bg-blue-500 text-white border-blue-500 shadow-lg scale-110'
  }
  
  const inactiveStyle = 'bg-gray-100 dark:bg-gray-600 text-gray-400 border-2 border-gray-300 dark:border-gray-500'
  
  if (isCurrentPhase) {
    return `${baseClasses} ${activeStyles[phase]}`
  }
  
  // Show normal styling for phases that have been reached
  const phaseOrder = ['advance', 'retracement', 'decline', 'recovery']
  const currentIndex = phaseOrder.indexOf(systemState.value?.current_phase || 'advance')
  const thisIndex = phaseOrder.indexOf(phase)
  
  if (thisIndex <= currentIndex) {
    return `${baseClasses} ${phaseStyles[phase]}`
  }
  
  return `${baseClasses} ${inactiveStyle}`
}
</script>