import styled, { css } from "styled-components";

export const Card = styled.div`
  background: ${({ theme }) => theme.colors.surface};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radius};
  padding: ${({ theme }) => theme.space(5)};
`;

export const Button = styled.button<{ $variant?: "primary" | "ghost" }>`
  appearance: none;
  border-radius: 8px;
  border: 1px solid ${({ theme }) => theme.colors.border};
  padding: ${({ theme }) => theme.space(2)} ${({ theme }) => theme.space(4)};
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
  ${({ theme, $variant }) =>
    $variant === "primary"
      ? css`
          background: ${theme.colors.accent};
          border-color: ${theme.colors.accent};
          color: #04101f;
          &:hover:not(:disabled) {
            background: ${theme.colors.accentHover};
          }
        `
      : css`
          background: transparent;
          color: ${theme.colors.text};
          &:hover:not(:disabled) {
            border-color: ${theme.colors.accent};
          }
        `}
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

export const Input = styled.input`
  width: 100%;
  background: ${({ theme }) => theme.colors.bg};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: 8px;
  color: ${({ theme }) => theme.colors.text};
  padding: ${({ theme }) => theme.space(2)} ${({ theme }) => theme.space(3)};
  font-size: 14px;
  &:focus {
    outline: none;
    border-color: ${({ theme }) => theme.colors.accent};
  }
`;

export const Textarea = styled.textarea`
  width: 100%;
  min-height: 80px;
  resize: vertical;
  background: ${({ theme }) => theme.colors.bg};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: 8px;
  color: ${({ theme }) => theme.colors.text};
  padding: ${({ theme }) => theme.space(2)} ${({ theme }) => theme.space(3)};
  font-size: 14px;
  font-family: inherit;
  &:focus {
    outline: none;
    border-color: ${({ theme }) => theme.colors.accent};
  }
`;

export const Label = styled.label`
  display: block;
  font-weight: 600;
  margin-bottom: ${({ theme }) => theme.space(1)};
`;

export const Field = styled.div`
  margin-bottom: ${({ theme }) => theme.space(4)};
`;

export const ErrorText = styled.span`
  color: ${({ theme }) => theme.colors.danger};
  font-size: 12.5px;
`;

export const Muted = styled.span`
  color: ${({ theme }) => theme.colors.textMuted};
`;
