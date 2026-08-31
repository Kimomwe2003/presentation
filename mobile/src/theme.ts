/**
 * Minimal design tokens. Extended in later prompts; keeps components consistent.
 */
export const colors = {
  primary: '#0B6E4F',
  primaryDark: '#095B42',
  onPrimary: '#FFFFFF',
  background: '#F7F8FA',
  surface: '#FFFFFF',
  border: '#E1E4E8',
  text: '#1B1F24',
  textSecondary: '#5C636A',
  error: '#B3261E',
  errorSurface: '#FDEBEA',
  success: '#2E7D32',
  disabled: '#B9BEC4',
  overlay: 'rgba(0, 0, 0, 0.35)',
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
};

export const radii = {
  sm: 8,
  md: 12,
  lg: 16,
  round: 999,
};

export const typography = {
  title: { fontSize: 26, fontWeight: '700' as const, color: colors.text },
  subtitle: { fontSize: 16, color: colors.textSecondary },
  body: { fontSize: 15, color: colors.text },
  label: { fontSize: 13, color: colors.textSecondary },
};

// ReuseHub design system — Slate monochromatic palette.
export const slate = {
  primary: '#0F172A',
  secondary: '#64748B',
  border: '#E2E8F0',
  placeholder: '#CBD5E1',
  accent: '#F8FAFC',
  grid: '#F1F5F9',
  white: '#FFFFFF',
  line: '#94A3B8',
  lineSoft: '#CBD5E1',
  glow: 'rgba(15, 23, 42, 0.05)',
  shadow: 'rgba(15, 23, 42, 0.1)',
};
