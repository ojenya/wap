import type { RunEvent, RunStatus } from "@wap/shared";
import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

type Props = {
  events: RunEvent[];
  runStatus: RunStatus | string;
};

function kindTone(kind: string): string {
  if (kind === "stage_error" || kind === "vm_error" || kind === "scm_error") {
    return "border-red-400 bg-red-50 text-red-700";
  }
  if (kind === "hitl") return "border-amber-400 bg-amber-50 text-amber-800";
  if (kind === "stage_complete") return "border-emerald-400 bg-white text-emerald-700";
  if (kind === "stage_start") return "border-sky-400 bg-white text-sky-700";
  return "border-neutral-300 bg-white text-neutral-600";
}

function isActiveEvent(event: RunEvent, events: RunEvent[], runStatus: string): boolean {
  const activeRun = runStatus === "pending" || runStatus === "running";
  if (!activeRun) return false;
  const last = events[events.length - 1];
  if (!last || last.id !== event.id) return false;
  return event.kind === "stage_start" || event.kind === "run";
}

export function RunTimeline({ events, runStatus }: Props) {
  if (!events.length) {
    return <p className="text-sm text-muted-foreground">No events yet.</p>;
  }

  const showLoadingTail =
    runStatus === "running" || runStatus === "pending" || runStatus === "awaiting_approval";

  return (
    <ol className="relative ms-2 space-y-0 border-s border-neutral-200 ps-6">
      {events.map((event, index) => {
        const active = isActiveEvent(event, events, String(runStatus));
        const time = new Date(event.created_at).toLocaleTimeString();
        return (
          <li key={event.id} className="relative pb-5 last:pb-0">
            <span
              className={cn(
                "absolute -start-[31px] top-1 flex h-4 w-4 items-center justify-center rounded-full border-2 bg-white",
                active ? "border-sky-500" : "border-neutral-300",
              )}
            >
              {active ? (
                <Loader2 className="h-3 w-3 animate-spin text-sky-600" />
              ) : (
                <span
                  className={cn(
                    "h-2 w-2 rounded-full",
                    event.kind.includes("error")
                      ? "bg-red-500"
                      : event.kind === "stage_complete"
                        ? "bg-emerald-500"
                        : "bg-sky-500",
                  )}
                />
              )}
            </span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                <span
                  className={cn(
                    "inline-flex rounded-md border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide",
                    kindTone(event.kind),
                  )}
                >
                  {event.kind}
                </span>
                {event.stage_name && (
                  <span className="text-xs font-medium text-foreground">{event.stage_name}</span>
                )}
                <span className="ms-auto text-[11px] text-muted-foreground">{time}</span>
              </div>
              <p className="mt-1 text-sm leading-snug text-foreground/90">{event.message}</p>
              {index === events.length - 1 &&
                runStatus === "awaiting_approval" &&
                event.kind !== "run" && (
                  <p className="mt-1 text-xs text-amber-700">Waiting for approval…</p>
                )}
            </div>
          </li>
        );
      })}
      {showLoadingTail && runStatus === "running" && (
        <li className="relative pb-0">
          <span className="absolute -start-[31px] top-1 flex h-4 w-4 items-center justify-center rounded-full border-2 border-sky-500 bg-white">
            <Loader2 className="h-3 w-3 animate-spin text-sky-600" />
          </span>
          <p className="text-sm text-muted-foreground">Recording…</p>
        </li>
      )}
    </ol>
  );
}
