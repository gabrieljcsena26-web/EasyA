import { render, screen } from '@testing-library/react';
import App from './App';

test('renders app title', () => {
  render(<App />);
  // App renders a unique title 'EasyAgenda'
  const title = screen.getByRole('heading', { name: /EasyAgenda/i });
  expect(title).toBeInTheDocument();
});
