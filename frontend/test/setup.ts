import { vi } from 'vitest'

// Mock Nuxt composables
vi.mock('#app', () => ({
  useRoute: vi.fn(() => ({
    params: { id: '1' }
  })),
  useRouter: vi.fn(() => ({
    push: vi.fn()
  })),
  navigateTo: vi.fn()
}))

// Mock NuxtLink
vi.mock('#components', () => ({
  NuxtLink: {
    name: 'NuxtLink',
    template: '<a><slot /></a>'
  }
}))