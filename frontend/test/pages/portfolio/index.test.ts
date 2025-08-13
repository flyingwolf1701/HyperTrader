import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import PortfolioIndex from '../../../app/pages/portfolio/index.vue'

// Mock NuxtLink
const NuxtLink = {
  name: 'NuxtLink',
  props: ['to'],
  template: '<a :href="to"><slot /></a>'
}

describe('Portfolio Index Page', () => {
  const mountOptions = {
    global: {
      components: {
        NuxtLink
      }
    }
  }

  it('should display portfolio summary cards', () => {
    const wrapper = mount(PortfolioIndex, mountOptions)
    
    expect(wrapper.find('.portfolio-summary').exists()).toBe(true)
    expect(wrapper.find('.summary-cards').exists()).toBe(true)
    expect(wrapper.findAll('.summary-card')).toHaveLength(4)
  })

  it('should show total portfolio value', () => {
    const wrapper = mount(PortfolioIndex, mountOptions)
    
    const totalValueCard = wrapper.find('.summary-card')
    expect(totalValueCard.text()).toContain('Total Portfolio Value')
    expect(totalValueCard.text()).toContain('$125,000')
  })

  it('should display cash reserves percentage', () => {
    const wrapper = mount(PortfolioIndex, mountOptions)
    
    const summaryCards = wrapper.findAll('.summary-card')
    const cashCard = summaryCards[1]
    expect(cashCard.text()).toContain('Cash Reserves')
    expect(cashCard.text()).toContain('25.0% of portfolio')
  })

  it('should render allocation management section', () => {
    const wrapper = mount(PortfolioIndex, mountOptions)
    
    expect(wrapper.find('.allocation-management').exists()).toBe(true)
    expect(wrapper.find('.allocation-grid').exists()).toBe(true)
  })

  it('should display allocation cards for each position', () => {
    const wrapper = mount(PortfolioIndex, mountOptions)
    
    const allocationCards = wrapper.findAll('.allocation-card')
    expect(allocationCards.length).toBeGreaterThan(0)
    
    const firstCard = allocationCards[0]
    expect(firstCard.text()).toContain('BTC')
    expect(firstCard.text()).toContain('25%')
  })

  it('should show allocation status (balanced, over-allocated, under-allocated)', () => {
    const wrapper = mount(PortfolioIndex, mountOptions)
    
    const statusElements = wrapper.findAll('.status')
    expect(statusElements.length).toBeGreaterThan(0)
    
    const statuses = statusElements.map(el => el.text())
    expect(statuses).toEqual(
      expect.arrayContaining(['over-allocated', 'under-allocated', 'balanced'])
    )
  })

  it('should have rebalance functionality', () => {
    const wrapper = mount(PortfolioIndex, mountOptions)
    
    const rebalanceButtons = wrapper.findAll('button').filter(btn => 
      btn.text().includes('Rebalance')
    )
    expect(rebalanceButtons.length).toBeGreaterThan(0)
  })

  it('should trigger rebalance when button is clicked', async () => {
    const wrapper = mount(PortfolioIndex, mountOptions)
    const consoleSpy = vi.spyOn(console, 'log').mockImplementation(() => {})
    
    const rebalanceButton = wrapper.find('button[data-testid="rebalance-btc"]')
    
    await rebalanceButton.trigger('click')
    expect(consoleSpy).toHaveBeenCalledWith('Rebalancing:', 'BTC')
    
    consoleSpy.mockRestore()
  })

  it('should have emergency exit functionality', () => {
    const wrapper = mount(PortfolioIndex, mountOptions)
    
    const emergencyButton = wrapper.findAll('button').find(btn =>
      btn.text().includes('Emergency Exit')
    )
    expect(emergencyButton?.exists()).toBe(true)
  })

  it('should display positive and negative changes correctly', () => {
    const wrapper = mount(PortfolioIndex, mountOptions)
    
    const positiveElements = wrapper.findAll('.positive')
    const negativeElements = wrapper.findAll('.negative')
    
    expect(positiveElements.length).toBeGreaterThan(0)
    expect(negativeElements.length).toBeGreaterThan(0)
  })
})