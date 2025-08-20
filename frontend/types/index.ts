// frontend/types/index.ts

/**
 * Defines the TypeScript interface for the SystemState object.
 * This must be kept in sync with the Pydantic model on the backend.
 * Using string for decimal values is crucial to avoid floating-point precision errors in JavaScript.
 */
export interface SystemState {
  // --- Core Identifiers ---
  symbol: string;
  current_phase: 'advance' | 'retracement' | 'decline' | 'recovery';

  // --- Financial State (as strings to preserve decimal precision) ---
  entry_price: string;
  unit_value: string;
  long_invested: string;
  long_cash: string;
  hedge_long: string;
  hedge_short: string;
  initial_margin: string;

  // --- Unit & Price Tracking ---
  current_unit: number;
  peak_unit: number;
  peak_price: string;
  valley_unit: number | null;
  valley_price: string | null;
}