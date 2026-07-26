import { Camera, Loader2, Play, RefreshCw, Shield, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";

import { api } from "@/api/client";
import {
  useCreateEnvironment,
  useDeleteEnvironment,
  useEnvironments,
  useRefreshEnvironment,
} from "@/api/hooks";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { VmInstance } from "@wap/shared";

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
  const remove = useDeleteEnvironment();
  const [error, setError] = useState<string | null>(null);
  const [caps, setCaps] = useState<Caps | null>(null);
  const [busyVm, setBusyVm] = useState<string | null>(null);
  const [vmsByEnv, setVmsByEnv] = useState<Record<string, VmInstance[]>>({});
  const [shotPreview, setShotPreview] = useState<Record<string, string>>({});
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

  async function loadVms(envId: string) {
    const list = await api.listVms(envId);
    setVmsByEnv((prev) => ({ ...prev, [envId]: list }));
    return list;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Environments</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Firecracker microVMs (or local jail fallback) with boot / snapshot / restore.
          Screenshots live under{" "}
          <code className="text-xs">data/artifacts/vms/&lt;id&gt;/</code> — not inside{" "}
          <code className="text-xs">data/vms/</code> (that folder is the VM disk/socket).
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
            <CardContent className="space-y-3 py-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
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
                        await loadVms(env.id);
                        await envs.refetch();
                      } finally {
                        setBusyVm(null);
                      }
                    }}
                  >
                    <Play className="h-4 w-4" />
                    Boot VM
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={remove.isPending}
                    onClick={async () => {
                      if (!window.confirm(`Delete environment “${env.name}”?`)) return;
                      await remove.mutateAsync(env.id);
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                    Delete
                  </Button>
                </div>
              </div>

              <div className="rounded-lg border border-black/5 bg-[#f7f7f8] p-3">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <span className="text-xs font-medium text-muted-foreground">VM instances</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs"
                    onClick={() => loadVms(env.id)}
                  >
                    Reload
                  </Button>
                </div>
                {(vmsByEnv[env.id] ?? []).length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    No VMs listed yet — boot one, or click Reload.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {(vmsByEnv[env.id] ?? []).map((vm) => (
                      <li
                        key={vm.id}
                        className="flex flex-wrap items-center justify-between gap-2 text-xs"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <StatusBadge value={vm.status} />
                          <span className="font-mono">{vm.id.slice(0, 8)}</span>
                          <span className="text-muted-foreground">{vm.backend}</span>
                        </div>
                        <div className="flex flex-wrap gap-1">
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-7"
                            disabled={busyVm === vm.id}
                            onClick={async () => {
                              setBusyVm(vm.id);
                              try {
                                await api.screenshotVm(env.id, vm.id);
                                setShotPreview((prev) => ({
                                  ...prev,
                                  [vm.id]: `${api.vmScreenshotUrl(env.id, vm.id)}?t=${Date.now()}`,
                                }));
                              } finally {
                                setBusyVm(null);
                              }
                            }}
                          >
                            <Camera className="h-3.5 w-3.5" />
                            Screenshot
                          </Button>
                          {vm.status === "running" && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7"
                              onClick={async () => {
                                await api.destroyVm(env.id, vm.id);
                                await loadVms(env.id);
                              }}
                            >
                              Destroy
                            </Button>
                          )}
                        </div>
                        {shotPreview[vm.id] && (
                          <a
                            href={shotPreview[vm.id]}
                            target="_blank"
                            rel="noreferrer"
                            className="basis-full"
                          >
                            <img
                              src={shotPreview[vm.id]}
                              alt={`Screenshot ${vm.id.slice(0, 8)}`}
                              className="mt-1 max-h-40 rounded-md border border-black/5 object-contain"
                            />
                          </a>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
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
