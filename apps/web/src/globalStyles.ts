import { createGlobalStyle } from "styled-components";

export const GlobalStyle = createGlobalStyle`
  *, *::before, *::after { box-sizing: border-box; }
  html, body, #root { height: 100%; margin: 0; }
  body {
    background: ${({ theme }) => theme.colors.bg};
    color: ${({ theme }) => theme.colors.text};
    font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    font-size: 14px;
    line-height: 1.5;
  }
  a { color: ${({ theme }) => theme.colors.accent}; text-decoration: none; }
  a:hover { color: ${({ theme }) => theme.colors.accentHover}; }
  h1, h2, h3 { margin: 0 0 ${({ theme }) => theme.space(3)}; }
  pre {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 12.5px;
    white-space: pre-wrap;
    word-break: break-word;
  }
`;
