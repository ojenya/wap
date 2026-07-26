import styled from "styled-components";

type Tone = "neutral" | "success" | "warning" | "danger" | "accent";

const toneMap: Record<string, Tone> = {
  completed: "success",
  running: "accent",
  pending: "neutral",
  failed: "danger",
  skipped: "neutral",
  low: "success",
  medium: "warning",
  high: "danger",
};

const Badge = styled.span<{ $tone: Tone }>`
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: 999px;
  text-transform: capitalize;
  color: ${({ theme, $tone }) =>
    $tone === "neutral" ? theme.colors.textMuted : theme.colors[$tone]};
  border: 1px solid
    ${({ theme, $tone }) =>
      $tone === "neutral" ? theme.colors.border : theme.colors[$tone]};
  background: ${({ theme }) => theme.colors.surfaceAlt};
`;

export function StatusBadge({ value }: { value: string }) {
  return <Badge $tone={toneMap[value] ?? "neutral"}>{value}</Badge>;
}
