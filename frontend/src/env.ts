/**
 * Environment abstraction for Vite and Jest compatibility.
 * Uses Vite's import.meta.env in production, falls back to process.env for Jest/Node.
 */

const isVite = typeof import.meta !== 'undefined' && import.meta && import.meta.env;

const env = {
  get DEV(): boolean {
    return isVite
      ? (import.meta.env?.DEV ?? false)
      : (process.env.NODE_ENV === 'development');
  },
  get VITE_USE_TEST_DB(): boolean {
    return isVite
      ? (import.meta.env?.VITE_USE_TEST_DB === 'true')
      : (process.env.VITE_USE_TEST_DB === 'true');
  },
};

export default env;
