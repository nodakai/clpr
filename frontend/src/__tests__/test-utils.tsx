import React from 'react';
import { render, RenderResult } from '@testing-library/react';
import type { ReactElement } from 'react';

interface CustomRenderOptions<P = any> {
  wrapper?: React.ComponentType<{ children?: React.ReactNode }>;
  [key: string]: any;
}

/**
 * Custom render function for testing React components
 * Automatically includes helpful utilities and can wrap components with providers
 */
function customRender<P = any>(
  ui: ReactElement<P>,
  options?: CustomRenderOptions<P>
): RenderResult {
  const { wrapper: Wrapper, ...restOptions } = options || {};

  if (Wrapper) {
    return render(ui, {
      ...restOptions,
      wrapper: Wrapper,
    });
  }

  return render(ui, {
    ...restOptions,
  });
}

// Re-export everything from testing library
export * from '@testing-library/react';

// Override default render
export { customRender as render };

// Common helpers for this project
export const waitForLoadingToFinish = async () => {
  // Wait for any debounced queries to complete (300ms + buffer)
  await new Promise(resolve => setTimeout(resolve, 400));
};

export const getByTextContent = (container: HTMLElement, text: string) => {
  return container.querySelector(`[data-text="${text}"]`) ||
    Array.from(container.querySelectorAll('*')).find(
      el => el.textContent === text
    ) as HTMLElement;
};

export const findAllByRole = (container: HTMLElement, role: string) => {
  return container.querySelectorAll(`[role="${role}"]`);
};

export const simulateDarkMode = (enable: boolean) => {
  // Mock localStorage
  const localStorageMock = (() => {
    let store: Record<string, string> = {};
    return {
      getItem: (key: string) => store[key] || null,
      setItem: (key: string, value: string) => {
        store[key] = value.toString();
      },
      removeItem: (key: string) => {
        delete store[key];
      },
      clear: () => {
        store = {};
      },
    };
  })();
  Object.defineProperty(window, 'localStorage', { value: localStorageMock });

  // Set dark mode in localStorage
  localStorageMock.setItem('darkMode', JSON.stringify(enable));

  // Mock matchMedia
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: jest.fn().mockImplementation(query => ({
      matches: query === '(prefers-color-scheme: dark)' ? enable : !enable,
      media: query,
      onchange: null,
      addListener: jest.fn(),
      removeListener: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      dispatchEvent: jest.fn(),
    })),
  });
};
