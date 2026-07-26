import { Link, Outlet } from "react-router-dom";
import styled from "styled-components";

const Shell = styled.div`
  max-width: 1080px;
  margin: 0 auto;
  padding: ${({ theme }) => theme.space(8)} ${({ theme }) => theme.space(6)};
`;

const Header = styled.header`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.space(3)};
  margin-bottom: ${({ theme }) => theme.space(8)};
`;

const Logo = styled(Link)`
  font-size: 20px;
  font-weight: 700;
  color: ${({ theme }) => theme.colors.text};
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.space(2)};
`;

const Dot = styled.span`
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: ${({ theme }) => theme.colors.accent};
  box-shadow: 0 0 12px ${({ theme }) => theme.colors.accent};
`;

const Tagline = styled.span`
  color: ${({ theme }) => theme.colors.textMuted};
  font-size: 13px;
`;

export function App() {
  return (
    <Shell>
      <Header>
        <Logo to="/">
          <Dot />
          Change Factory
        </Logo>
        <Tagline>deterministic multi-agent workflow orchestrator</Tagline>
      </Header>
      <Outlet />
    </Shell>
  );
}
