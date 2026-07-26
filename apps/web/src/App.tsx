import {
  Activity,
  BookOpen,
  Box,
  GitBranch,
  LayoutDashboard,
  ListTodo,
  Settings2,
  Sparkles,
  Zap,
} from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

import { cn } from "@/lib/utils";

const nav = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/tasks", label: "Tasks", icon: ListTodo },
  { to: "/repositories", label: "Repositories", icon: GitBranch },
  { to: "/environments", label: "Environments", icon: Box },
  { to: "/automations", label: "Automations", icon: Zap },
  { to: "/learning", label: "Learning", icon: BookOpen },
  { to: "/settings", label: "Workflow", icon: Settings2 },
];

export function App() {
  return (
    <div className="flex min-h-screen bg-[#f9f9f9]">
      <aside className="sticky top-0 flex h-screen w-[260px] shrink-0 flex-col border-r border-black/5 bg-[#f7f7f8] px-3 py-4">
        <div className="mb-6 flex items-center gap-2 px-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-black text-white">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <div className="text-sm font-semibold tracking-tight">Change Factory</div>
            <div className="text-xs text-muted-foreground">multi-agent platform</div>
          </div>
        </div>
        <nav className="flex flex-1 flex-col gap-1">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-foreground/80 transition-colors hover:bg-black/[0.04]",
                  isActive && "bg-white text-foreground shadow-sm",
                )
              }
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="flex items-start gap-2 rounded-xl bg-white p-3 text-xs text-muted-foreground shadow-sm">
          <Activity className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          Env snapshots · artifacts · HITL · MCP · GitHub/GitLab
        </div>
      </aside>
      <main className="flex-1 overflow-auto">
        <div className="mx-auto max-w-5xl px-8 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
