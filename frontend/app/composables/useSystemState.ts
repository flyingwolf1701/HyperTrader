// frontend/composables/useSystemState.ts

import { useState } from '#app';
import type { SystemState } from '~/types';

/**
 * A Nuxt composable for managing the global SystemState.
 * This provides a single, reactive source of truth for the entire UI.
 * Any component can use this composable to access the latest trading state.
 *
 * @returns A reactive reference to the current SystemState or null.
 */
export const useSystemState = () => {
  // useState creates a reactive state that is shared across components and is SSR-friendly.
  // 'systemState' is the unique key for this state.
  return useState<SystemState | null>('systemState', () => null);
};