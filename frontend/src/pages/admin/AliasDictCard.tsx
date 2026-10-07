import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRef, useState } from 'react';
import { Download, Layers, Plus, Search, Trash2, Upload } from 'lucide-react';
import { toast } from 'sonner';
import Badge from '../../components/ui/Badge';
import Button from '../../components/ui/Button';
import { Card, CardBody, CardHeader } from '../../components/ui/Card';
import { LoadingBlock } from '../../components/ui/Feedback';
import {
  adminAddAlias,
  adminDeleteAlias,
  adminExportAliases,
  adminGetAliases,
  adminListAliasEntries,
  adminSchemaFields,
  adminUploadAliases,
  type AliasEntry,
} from '../../api/auth';

// Column-name alias dictionary: admins upload a two-column CSV (field, comma-
// separated aliases), or browse/search/add/remove individual aliases. Merged
// with the engine's built-in dictionary and applied on the next harmonize.
export function AliasDictCard() {
  const qc = useQueryClient();
  const status = useQuery({ queryKey: ['admin', 'schema-aliases'], queryFn: adminGetAliases });
  const fields = useQuery({ queryKey: ['admin', 'schema-fields'], queryFn: adminSchemaFields });
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [query, setQuery] = useState('');
  const [addSource, setAddSource] = useState('');
  const [addField, setAddField] = useState('');

  const entries = useQuery({
    queryKey: ['admin', 'alias-entries', query],
    queryFn: () => adminListAliasEntries(query, 500),
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['admin', 'schema-aliases'] });
    qc.invalidateQueries({ queryKey: ['admin', 'alias-entries'] });
  };

  const uploadM = useMutation({
    mutationFn: () => adminUploadAliases(file!),
    onSuccess: (s) => {
      refresh();
      toast.success(`Loaded ${s.alias_count} aliases across ${s.field_count} fields`);
      setFile(null);
      if (fileRef.current) fileRef.current.value = '';
    },
    onError: (e: any) => toast.error(e?.message ?? 'Could not upload aliases'),
  });

  const addM = useMutation({
    mutationFn: () => adminAddAlias(addSource.trim(), addField.trim()),
    onSuccess: () => {
      refresh();
      toast.success('Alias added');
      setAddSource('');
      setAddField('');
    },
    onError: (e: any) => toast.error(e?.message ?? 'Could not add alias'),
  });

  const delM = useMutation({
    mutationFn: (e: AliasEntry) => adminDeleteAlias(e.source, e.field_name),
    onSuccess: () => {
      refresh();
      toast.success('Alias removed');
    },
    onError: (e: any) => toast.error(e?.message ?? 'Could not remove alias'),
  });

  const fieldList = fields.data?.fields ?? [];
  const unknownField = addField.trim() !== '' && !fieldList.includes(addField.trim());
  const rows = entries.data?.entries ?? [];

  return (
    <Card>
      <CardHeader
        icon={<Layers className="h-4 w-4" />}
        title="Column-name aliases"
        description="Nicknames that teach the schema mapper to recognise messy headers. Uploads and manual edits are merged with the engine's built-in dictionary and applied on the next harmonize."
      />
      <CardBody className="space-y-4">
        <div className="text-sm text-slate-600 dark:text-slate-300">
          {status.data?.present ? (
            <span>
              Custom dictionary: <strong>{status.data.alias_count}</strong> admin aliases across{' '}
              <strong>{status.data.field_count}</strong> fields — merged with the built-ins.
            </span>
          ) : (
            <span className="text-slate-400">
              No custom aliases yet — the schema mapper uses its built-in dictionary.
            </span>
          )}
        </div>

        {/* Bulk upload */}
        <form
          className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-100 bg-slate-50/60 p-3 dark:border-slate-800 dark:bg-slate-800/40"
          onSubmit={(e) => {
            e.preventDefault();
            if (file) uploadM.mutate();
          }}
        >
          <div>
            <label htmlFor="alias-file" className="block text-xs font-medium text-slate-500">
              Bulk upload — CSV (field, comma-separated aliases)
            </label>
            <input
              id="alias-file"
              ref={fileRef}
              type="file"
              accept=".csv,.tsv,.txt"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="mt-1 text-sm file:mr-2 file:rounded file:border-0 file:bg-primary-50 file:px-2 file:py-1 file:text-primary-700 dark:file:bg-primary-500/15 dark:file:text-primary-300"
            />
          </div>
          <Button type="submit" loading={uploadM.isPending} disabled={!file} icon={<Upload className="h-4 w-4" />}>
            Upload
          </Button>
        </form>

        {/* Add one */}
        <form
          className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-100 bg-slate-50/60 p-3 dark:border-slate-800 dark:bg-slate-800/40"
          onSubmit={(e) => {
            e.preventDefault();
            if (addSource.trim() && addField.trim()) addM.mutate();
          }}
        >
          <div>
            <label htmlFor="alias-source" className="block text-xs font-medium text-slate-500">
              Alias (nickname)
            </label>
            <input
              id="alias-source"
              value={addSource}
              onChange={(e) => setAddSource(e.target.value)}
              placeholder="e.g. patient_sex"
              className="mt-1 w-40 rounded border border-slate-200 px-2 py-1.5 text-sm focus:border-primary-400 focus:outline-none dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
            />
          </div>
          <div>
            <label htmlFor="alias-field" className="block text-xs font-medium text-slate-500">
              Canonical field
            </label>
            <input
              id="alias-field"
              list="schema-fields-list"
              value={addField}
              onChange={(e) => setAddField(e.target.value)}
              placeholder="e.g. sex"
              className={`mt-1 w-40 rounded border px-2 py-1.5 text-sm focus:outline-none dark:bg-slate-900 dark:text-slate-200 ${
                unknownField ? 'border-amber-400' : 'border-slate-200 focus:border-primary-400 dark:border-slate-700'
              }`}
            />
            <datalist id="schema-fields-list">
              {fieldList.map((f) => (
                <option key={f} value={f} />
              ))}
            </datalist>
          </div>
          <Button
            type="submit"
            loading={addM.isPending}
            disabled={!addSource.trim() || !addField.trim()}
            icon={<Plus className="h-4 w-4" />}
          >
            Add
          </Button>
          {unknownField && (
            <span className="text-xs text-amber-600">
              &ldquo;{addField.trim()}&rdquo; isn&rsquo;t a known schema field — the mapper will ignore it.
            </span>
          )}
        </form>

        {/* Browse + search */}
        <div>
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <div className="relative max-w-xs flex-1">
              <Search className="pointer-events-none absolute left-2 top-2.5 h-4 w-4 text-slate-400" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search aliases or fields…"
                className="w-full rounded border border-slate-200 py-1.5 pl-8 pr-2 text-sm focus:border-primary-400 focus:outline-none dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
              />
            </div>
            <button
              type="button"
              onClick={() =>
                adminExportAliases('merged').catch(() => toast.error('Export failed'))
              }
              className="inline-flex items-center gap-1.5 rounded border border-slate-200 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
              title="Download the full (built-in + custom) alias dictionary as CSV"
            >
              <Download className="h-4 w-4" />
              Export all
            </button>
            <button
              type="button"
              onClick={() =>
                adminExportAliases('custom').catch(() => toast.error('Export failed'))
              }
              className="inline-flex items-center gap-1.5 rounded border border-slate-200 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
              title="Download only the admin-added (custom) aliases as CSV"
            >
              <Download className="h-4 w-4" />
              Export custom
            </button>
          </div>
          {entries.isLoading ? (
            <LoadingBlock />
          ) : rows.length === 0 ? (
            <p className="py-6 text-center text-sm text-slate-400">No aliases match.</p>
          ) : (
            <div className="max-h-72 overflow-y-auto rounded-lg border border-slate-100 dark:border-slate-800">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-slate-50 dark:bg-slate-800">
                  <tr className="text-left text-xs uppercase tracking-wide text-slate-400">
                    <th className="px-3 py-2">Alias</th>
                    <th className="px-3 py-2">Field</th>
                    <th className="px-3 py-2">Source</th>
                    <th className="px-3 py-2 text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={`${r.source}::${r.field_name}`} className="border-t border-slate-50 dark:border-slate-800/60">
                      <td className="px-3 py-1.5 font-mono text-xs text-slate-700 dark:text-slate-300">{r.source}</td>
                      <td className="px-3 py-1.5 text-slate-700 dark:text-slate-300">{r.field_name}</td>
                      <td className="px-3 py-1.5">
                        <Badge tone={r.builtin ? 'slate' : 'primary'}>{r.builtin ? 'built-in' : 'custom'}</Badge>
                      </td>
                      <td className="px-3 py-1.5 text-right">
                        {r.builtin ? (
                          <span className="text-xs text-slate-300">—</span>
                        ) : (
                          <button
                            title="Remove alias"
                            onClick={() => delM.mutate(r)}
                            className="rounded p-1 text-rose-500 hover:bg-rose-50 dark:text-rose-400 dark:hover:bg-rose-500/10"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="mt-1 text-xs text-slate-400">
            Showing {entries.data?.returned ?? 0} of {entries.data?.total ?? 0}. Built-ins are read-only; custom rows can be removed.
          </p>
        </div>

        <p className="text-xs text-slate-400">
          Bulk row example: <code className="rounded bg-slate-100 px-1 dark:bg-slate-800">SEX,&quot;gender,patient_sex,gender_at_birth&quot;</code>
        </p>
      </CardBody>
    </Card>
  );
}
