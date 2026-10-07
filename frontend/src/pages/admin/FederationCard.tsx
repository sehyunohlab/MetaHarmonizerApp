import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRef } from 'react';
import { Download, Network, Upload } from 'lucide-react';
import { toast } from 'sonner';
import Badge from '../../components/ui/Badge';
import Button from '../../components/ui/Button';
import { Card, CardBody, CardHeader } from '../../components/ui/Card';
import { EmptyState, LoadingBlock } from '../../components/ui/Feedback';
import {
  approveFederationImport,
  exportFederationBundle,
  importFederationBundle,
  listFederationImports,
  rejectFederationImport,
  type FederationBundle,
} from '../../api/federation';

export function FederationCard() {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const imports = useQuery({
    queryKey: ['admin', 'federation-imports'],
    queryFn: listFederationImports,
  });
  const refresh = () => qc.invalidateQueries({ queryKey: ['admin', 'federation-imports'] });

  const importM = useMutation({
    mutationFn: importFederationBundle,
    onSuccess: (result) => {
      refresh();
      toast.success(`Staged ${result.mapping_count} shared decisions for review`);
    },
    onError: (error: any) => toast.error(error?.message ?? 'Could not import bundle'),
  });
  const approveM = useMutation({
    mutationFn: approveFederationImport,
    onSuccess: () => {
      refresh();
      toast.success('Imported decisions promoted to the shared knowledge base');
    },
    onError: (error: any) => toast.error(error?.message ?? 'Could not approve import'),
  });
  const rejectM = useMutation({
    mutationFn: rejectFederationImport,
    onSuccess: () => {
      refresh();
      toast('Federation import rejected');
    },
    onError: (error: any) => toast.error(error?.message ?? 'Could not reject import'),
  });

  const download = async () => {
    try {
      const bundle = await exportFederationBundle();
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `${bundle.source_instance}-shared-kb.json`;
      anchor.click();
      URL.revokeObjectURL(url);
      toast.success(`Downloaded ${bundle.payload.mappings.length} shared decisions`);
    } catch (error: any) {
      toast.error(error?.message ?? 'Could not export shared knowledge');
    }
  };

  const upload = async (file: File) => {
    try {
      const bundle = JSON.parse(await file.text()) as FederationBundle;
      importM.mutate(bundle);
    } catch {
      toast.error('Bundle must be valid JSON');
    } finally {
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const rows = imports.data ?? [];
  return (
    <Card>
      <CardHeader
        icon={<Network className="h-4 w-4" />}
        title="Federation-lite — shared knowledge exchange"
        description="Exchange signed, admin-promoted human decisions between trusted MetaHarmonizer installations. Personal decisions and machine proposals never leave this instance."
        action={
          <div className="flex items-center gap-2">
            <Button size="sm" variant="secondary" icon={<Download className="h-3.5 w-3.5" />} onClick={download}>
              Download bundle
            </Button>
            <input
              ref={fileRef}
              type="file"
              accept="application/json,.json"
              className="hidden"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void upload(file);
              }}
            />
            <Button
              size="sm"
              icon={<Upload className="h-3.5 w-3.5" />}
              loading={importM.isPending}
              onClick={() => fileRef.current?.click()}
            >
              Import bundle
            </Button>
          </div>
        }
      />
      <CardBody>
        {imports.isLoading ? (
          <LoadingBlock />
        ) : rows.length === 0 ? (
          <EmptyState
            icon={<Network className="h-6 w-6" />}
            title="No federation imports"
            description="Imported bundles remain pending until an administrator approves or rejects them."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs uppercase text-slate-400 dark:border-slate-800">
                  <th className="px-2 py-2">Source</th>
                  <th className="px-2 py-2">Decisions</th>
                  <th className="px-2 py-2">Status</th>
                  <th className="px-2 py-2">Received</th>
                  <th className="px-2 py-2 text-right">Review</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} className="border-b border-slate-50 dark:border-slate-800/60">
                    <td className="px-2 py-2 font-mono text-xs">{row.source_instance}</td>
                    <td className="px-2 py-2">{row.mapping_count}</td>
                    <td className="px-2 py-2">
                      <Badge tone={row.status === 'approved' ? 'green' : row.status === 'rejected' ? 'rose' : 'amber'}>
                        {row.status}
                      </Badge>
                    </td>
                    <td className="px-2 py-2 text-xs text-slate-500">
                      {row.created_at ? new Date(row.created_at).toLocaleString() : '—'}
                    </td>
                    <td className="px-2 py-2 text-right">
                      {row.status === 'pending' && (
                        <div className="inline-flex gap-2">
                          <Button
                            size="sm"
                            loading={approveM.isPending && approveM.variables === row.id}
                            onClick={() => approveM.mutate(row.id)}
                          >
                            Approve
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-rose-600"
                            loading={rejectM.isPending && rejectM.variables === row.id}
                            onClick={() => rejectM.mutate(row.id)}
                          >
                            Reject
                          </Button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
