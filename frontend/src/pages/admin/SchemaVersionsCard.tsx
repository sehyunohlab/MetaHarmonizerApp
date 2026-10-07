import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRef, useState } from 'react';
import { CheckCheck, GitCompare, Layers, Upload } from 'lucide-react';
import { toast } from 'sonner';
import Badge from '../../components/ui/Badge';
import Button from '../../components/ui/Button';
import { Card, CardBody, CardHeader } from '../../components/ui/Card';
import { EmptyState, LoadingBlock } from '../../components/ui/Feedback';
import { listEngineTargetSchemas } from '../../api/client';
import {
  adminDiffSchemaVersions,
  adminListSchemaVersions,
  adminPromoteSchemaVersion,
  adminUploadSchemaVersion,
  type SchemaDiff,
} from '../../api/auth';

export function SchemaVersionsCard() {
  const qc = useQueryClient();
  const engineSchemas = useQuery({ queryKey: ['engine-target-schemas'], queryFn: listEngineTargetSchemas });
  const [target, setTarget] = useState('');
  const activeTarget = target || engineSchemas.data?.[0]?.key || '';
  const versions = useQuery({
    queryKey: ['admin', 'schema-versions', activeTarget],
    queryFn: () => adminListSchemaVersions(activeTarget || undefined),
    enabled: !!activeTarget,
  });
  const fileRef = useRef<HTMLInputElement>(null);
  const [label, setLabel] = useState('');
  const [file, setFile] = useState<File | null>(null);

  // Schema diff (G6 layer A): compare two versions' curated-fields dictionaries.
  const [fromId, setFromId] = useState<number | null>(null);
  const [toId, setToId] = useState<number | null>(null);
  const [diff, setDiff] = useState<SchemaDiff | null>(null);
  const diffM = useMutation({
    mutationFn: () => adminDiffSchemaVersions(fromId!, toId!),
    onSuccess: setDiff,
    onError: (e: any) => toast.error(e?.message ?? 'Could not compute diff'),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ['admin', 'schema-versions'] });

  const uploadM = useMutation({
    mutationFn: () => adminUploadSchemaVersion(activeTarget, label.trim(), file!, true),
    onSuccess: (v) => {
      invalidate();
      toast.success(`Schema ${v.label} uploaded and promoted`);
      setLabel('');
      setFile(null);
      if (fileRef.current) fileRef.current.value = '';
    },
    onError: (e: any) => toast.error(e?.message ?? 'Could not upload schema version'),
  });

  const promoteM = useMutation({
    mutationFn: adminPromoteSchemaVersion,
    onSuccess: (v) => {
      invalidate();
      toast.success(`Schema ${v.label} is now current`);
    },
    onError: (e: any) => toast.error(e?.message ?? 'Could not promote version'),
  });

  return (
    <Card>
      <CardHeader
        icon={<Layers className="h-4 w-4" />}
        title="Schema versions"
        description="Each target schema keeps its own version lineage. New uploads are new versions of the selected target — existing studies stay pinned."
      />
      <CardBody className="space-y-4">
        {/* Target schema — each target has its own version lineage */}
        <div>
          <label htmlFor="schema-target" className="block text-xs font-medium text-slate-500">
            Target schema
          </label>
          <select
            id="schema-target"
            value={activeTarget}
            onChange={(e) => {
              setTarget(e.target.value);
              setFromId(null);
              setToId(null);
              setDiff(null);
            }}
            className="mt-1 rounded border border-slate-200 px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
          >
            {engineSchemas.data?.map((s) => (
              <option key={s.key} value={s.key}>{s.label}</option>
            ))}
          </select>
        </div>

        {/* Upload form */}
        <form
          className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-100 bg-slate-50/60 p-3 dark:border-slate-800 dark:bg-slate-800/40"
          onSubmit={(e) => {
            e.preventDefault();
            if (label.trim() && file && activeTarget) uploadM.mutate();
          }}
        >
          <div>
            <label htmlFor="schema-label" className="block text-xs font-medium text-slate-500">
              Version label
            </label>
            <input
              id="schema-label"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="e.g. v2"
              className="mt-1 w-28 rounded border border-slate-200 px-2 py-1.5 text-sm focus:border-primary-400 focus:outline-none dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
            />
          </div>
          <div>
            <label htmlFor="schema-file" className="block text-xs font-medium text-slate-500">
              Curated-fields CSV
            </label>
            <input
              id="schema-file"
              ref={fileRef}
              type="file"
              accept=".csv"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="mt-1 text-sm file:mr-2 file:rounded file:border-0 file:bg-primary-50 file:px-2 file:py-1 file:text-primary-700 dark:file:bg-primary-500/15 dark:file:text-primary-300"
            />
          </div>
          <Button
            type="submit"
            loading={uploadM.isPending}
            disabled={!label.trim() || !file || !activeTarget}
            icon={<Upload className="h-4 w-4" />}
          >
            Upload &amp; promote
          </Button>
        </form>

        {/* Versions list */}
        {versions.isLoading ? (
          <LoadingBlock label="Loading schema versions…" />
        ) : !versions.data?.length ? (
          <EmptyState title="No schema versions yet" />
        ) : (
          <ul className="divide-y divide-slate-100 dark:divide-slate-800">
            {versions.data.map((v) => (
              <li key={v.id} className="flex items-center justify-between gap-3 py-2.5">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm font-medium text-slate-800 dark:text-slate-200">{v.label}</span>
                  {v.is_current ? (
                    <Badge tone="green">
                      <CheckCheck className="h-3.5 w-3.5" />
                      Current
                    </Badge>
                  ) : null}
                  <span className="text-xs text-slate-400">
                    {new Date(v.created_at).toLocaleDateString()}
                  </span>
                </div>
                {!v.is_current && (
                  <Button
                    variant="secondary"
                    size="sm"
                    loading={promoteM.isPending && promoteM.variables === v.id}
                    onClick={() => promoteM.mutate(v.id)}
                  >
                    Make current
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}

        {/* Schema diff (G6 layer A) */}
        {(versions.data?.length ?? 0) >= 2 && (
          <div className="rounded-xl border border-slate-100 bg-slate-50/60 p-3 dark:border-slate-800 dark:bg-slate-800/40">
            <div className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-300">
              <GitCompare className="h-4 w-4" />
              Compare versions
            </div>
            <div className="flex flex-wrap items-end gap-2">
              <select
                aria-label="From version"
                value={fromId ?? ''}
                onChange={(e) => setFromId(Number(e.target.value) || null)}
                className="rounded border border-slate-200 px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
              >
                <option value="">From…</option>
                {versions.data!.map((v) => (
                  <option key={v.id} value={v.id}>{v.label}</option>
                ))}
              </select>
              <span className="text-slate-400">→</span>
              <select
                aria-label="To version"
                value={toId ?? ''}
                onChange={(e) => setToId(Number(e.target.value) || null)}
                className="rounded border border-slate-200 px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
              >
                <option value="">To…</option>
                {versions.data!.map((v) => (
                  <option key={v.id} value={v.id}>{v.label}</option>
                ))}
              </select>
              <Button
                variant="secondary"
                size="sm"
                loading={diffM.isPending}
                disabled={!fromId || !toId || fromId === toId}
                onClick={() => diffM.mutate()}
                icon={<GitCompare className="h-4 w-4" />}
              >
                Compare
              </Button>
            </div>

            {diff && (
              <div className="mt-3 space-y-2 text-sm">
                <p className="text-xs text-slate-500">
                  <span className="font-mono">{diff.from.label}</span> → <span className="font-mono">{diff.to.label}</span>:
                  {' '}{diff.summary.added} added · {diff.summary.removed} removed · {diff.summary.changed} changed · {diff.summary.unchanged} unchanged
                </p>
                {diff.added_fields.length > 0 && (
                  <div>
                    <span className="text-xs font-semibold text-emerald-700">Added fields</span>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {diff.added_fields.map((f) => (
                        <span key={f.field} className="rounded bg-emerald-50 px-1.5 py-0.5 font-mono text-xs text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300">
                          {f.field}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {diff.removed_fields.length > 0 && (
                  <div>
                    <span className="text-xs font-semibold text-red-700">Removed fields</span>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {diff.removed_fields.map((f) => (
                        <span key={f.field} className="rounded bg-red-50 px-1.5 py-0.5 font-mono text-xs text-red-700 line-through dark:bg-red-500/15 dark:text-red-300">
                          {f.field}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {diff.changed_fields.length > 0 && (
                  <div>
                    <span className="text-xs font-semibold text-amber-700">Changed allowed values</span>
                    <ul className="mt-1 space-y-1">
                      {diff.changed_fields.map((c) => (
                        <li key={c.field} className="text-xs">
                          <span className="font-mono font-medium text-slate-700 dark:text-slate-300">{c.field}</span>
                          {c.added_values.length > 0 && (
                            <span className="text-emerald-700"> +{c.added_values.join(', ')}</span>
                          )}
                          {c.removed_values.length > 0 && (
                            <span className="text-red-700"> −{c.removed_values.join(', ')}</span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {diff.summary.added === 0 && diff.summary.removed === 0 && diff.summary.changed === 0 && (
                  <p className="text-xs text-slate-400">No differences — the two schemas are identical.</p>
                )}
              </div>
            )}
          </div>
        )}
      </CardBody>
    </Card>
  );
}
