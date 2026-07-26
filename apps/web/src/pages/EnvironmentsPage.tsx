import { Loader2, Play, RefreshCw, Shield } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";

import { api } from "@/api/client";
import { useCreateEnvironment, useEnvironments, useRefreshEnvironment } from "@/api/hooks";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

type FormValues = {
  name: string;
  update_script: string;
  backend: string;
};

type Caps = {
  kvm: boolean;
  mode: string;
  can_boot_real: boolean;
  can_emulate: boolean;
  preferred_backend: string;
  reason: string;
  firecracker_bin: string | null;
};

export function EnvironmentsPage() {
  const envs = useEnvironments();
  const create = useCreateEnvironment();
  const refresh = useRefreshEnvironment();
  const [error, setError] = useState<string | null>(null);
  const [caps, setCaps] = useState<Caps | null>(null);
  const [busyVm, setBusyVm] = useState<string | null>(null);
  const form = useForm<FormValues>({
    defaultValues: {
      name: "",
      update_script: "pnpm install\npip install -e apps/api",
      backend: "firecracker",
    },
  });

  useEffect(() => {
    api.vmCapabilities().then(setCaps).catch(() => setCaps(null));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Environments</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Firecracker microVMs (or local jail fallback) with boot / snapshot / restore.
        </p>
      </div>

      {caps && (
        <Card>
          <CardContent className="flex flex-wrap items-center gap-3 py-4 text-sm">
            <Shield className="h-4 w-4" />
            <StatusBadge value={caps.preferred_backend} />
            <span className="text-muted-foreground">mode={caps.mode}</span>
            <span className="text-muted-foreground">
              kvm={String(caps.kvm)} real={String(caps.can_boot_real)} emulate=
              {String(caps.can_emulate)}
            </span>
            <span className="text-xs text-muted-foreground">{caps.reason}</span>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>New environment</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-3"
            onSubmit={form.handleSubmit(async (values) => {
              setError(null);
              try {
                await create.mutateAsync(values);
                form.reset({
                  name: "",
                  update_script: "pnpm install\npip install -e apps/api",
                  backend: "firecracker",
                });
              } catch (e) {
                setError(e instanceof Error ? e.message : "Failed");
              }
            })}
          >
            <div className="space-y-1.5">
              <Label htmlFor="name">Name</Label>
              <Input id="name" {...form.register("name", { required: true })} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="backend">Backend</Label>
              <Input id="backend" {...form.register("backend")} placeholder="firecracker|local" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="update_script">Update script</Label>
              <Textarea id="update_script" rows={4} {...form.register("update_script")} />
            </div>
            {error && <p className="text-xs text-destructive">{error}</p>}
            <Button type="submit" disabled={create.isPending}>
              {create.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              Create
            </Button>
          </form>
        </CardContent>
      </Card>

      <div className="space-y-3">
        {(envs.data ?? []).map((env) => (
          <Card key={env.id}>
            <CardContent className="flex flex-wrap items-start justify-between gap-3 py-4">
              <div>
                <div className="font-medium">{env.name}</div>
                <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
                  <StatusBadge value={env.status} />
                  <StatusBadge value={env.backend} />
                  {env.snapshot_id && <span>snapshot: {env.snapshot_id}</span>}
                  <span>
                    {env.vcpu_count} vCPU · {env.mem_size_mib} MiB
                  </span>
                </div>
                {env.last_error && (
                  <p className="mt-2 text-xs text-destructive">{env.last_error}</p>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => refresh.mutate(env.id)}
                  disabled={refresh.isPending}
                >
                  <RefreshCw className="h-4 w-4" />
                  Refresh snapshot
                </Button>
                <Button
                  size="sm"
                  disabled={busyVm === env.id}
                  onClick={async () => {
                    setBusyVm(env.id);
                    try {
                      await api.bootVm(env.id, {});
                      await envs.refetch();
                    } finally {
                      setBusyVm(null);
                    }
                  }}
                >
                  <Play className="h-4 w-4" />
                  Boot VM
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
        {!envs.data?.length && (
          <p className="text-sm text-muted-foreground">No environments yet.</p>
        )}
      </div>
    </div>
  );
}
