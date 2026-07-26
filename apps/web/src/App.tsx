import { GitBranch, LayoutDashboard, Sparkles } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

import { cn } from "@/lib/utils";

const nav = [
  { to: "/", label: "Tasks", icon: LayoutDashboard, end: true },
  { to: "/repositories", label: "Repositories", icon: GitBranch },
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
        <div className="rounded-xl bg-white p-3 text-xs text-muted-foreground shadow-sm">
          Connect a GitLab / Git repo, then run <span className="font-medium text-foreground">audit</span> or{" "}
          <span className="font-medium text-foreground">develop</span> in an isolated worktree.
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
