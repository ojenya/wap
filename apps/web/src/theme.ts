// Central design tokens for the styled-components theme.
export const theme = {
  colors: {
    bg: "#0d1117",
    surface: "#161b22",
    surfaceAlt: "#1c2330",
    border: "#2d333b",
    text: "#e6edf3",
    textMuted: "#8b949e",
    accent: "#58a6ff",
    accentHover: "#79b8ff",
    success: "#3fb950",
    warning: "#d29922",
    danger: "#f85149",
  },
  radius: "10px",
  space: (n: number) => `${n * 4}px`,
} as const;

export type AppTheme = typeof theme;
