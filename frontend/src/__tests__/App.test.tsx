import { jest } from '@jest/globals';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// Mock the database module
jest.unstable_mockModule('../db', () => ({
  database: {
    init: jest.fn().mockResolvedValue(undefined),
    query: jest.fn().mockResolvedValue([
      { service: 'ec2', region: 'us-east-1', instance_type: 'm5.large', vcpu: 2, memory_gb: 8, hourly: 0.096, os: 'Linux', purchase_option: 'OnDemand' },
    ]),
    close: jest.fn().mockResolvedValue(undefined),
    getBytesRead: jest.fn().mockResolvedValue(12345),
  },
}));

// Mock query-builder to control SQL generation
jest.unstable_mockModule('../query-builder', () => ({
  buildWhereClause: jest.fn(() => ({
    where: 'service = ?',
    params: ['ec2'],
  })),
}));

let App: any;

describe('App Integration', () => {
  beforeAll(async () => {
    const module = await import('../App');
    App = module.default;
  });

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders the header and filters', async () => {
    render(<App />);

    // Wait for database init and query to complete
    await waitFor(() => {
      expect(screen.getByText('AWS Pricing Calculator')).toBeInTheDocument();
    });

    // Check for filter panel - there may be multiple 'Service' and 'Region' labels
    const serviceElements = screen.getAllByText('Service');
    expect(serviceElements.length).toBeGreaterThan(0);
    const regionElements = screen.getAllByText('Region');
    expect(regionElements.length).toBeGreaterThan(0);
  });

  it('displays results after query execution', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('m5.large')).toBeInTheDocument();
    });

    // Price is formatted as $0.096/hr
    expect(screen.getByText('$0.096/hr')).toBeInTheDocument();
  });

  it('allows changing service filter', async () => {
    const user = userEvent.setup();
    render(<App />);

    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByText('AWS Pricing Calculator')).toBeInTheDocument();
    });

    // Find service select (assume it's a select element)
    const serviceSelect = screen.getByLabelText(/service/i) || screen.getByRole('combobox', { name: /service/i });
    if (serviceSelect) {
      await user.selectOptions(serviceSelect, 'rds');
      // Verify query builder was called with new filters (maybe later)
    }
  });

  it('toggles dark mode', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByLabelText(/Switch to dark mode/i)).toBeInTheDocument();
    });

    const themeToggle = screen.getByLabelText(/Switch to dark mode/i);
    await userEvent.click(themeToggle);

    // After toggle, should show opposite label
    expect(screen.getByLabelText(/Switch to light mode/i)).toBeInTheDocument();
  });

  it('displays query metrics', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/Query executed in \d+ms/)).toBeInTheDocument();
    });

    expect(screen.getByText(/Bytes: \d+/)).toBeInTheDocument();
  });
});
