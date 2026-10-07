import type { Dispatch, SetStateAction } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { Loader2, Search } from 'lucide-react';
import type { OntologySearchResult } from '../../api/types';
import type { EditState } from './types';

interface EditOntologyDialogProps {
  editState: EditState;
  searchQuery: string;
  searchResults: OntologySearchResult[];
  searching: boolean;
  busy: Record<number, boolean>;
  setEditState: Dispatch<SetStateAction<EditState | null>>;
  setSearchQuery: Dispatch<SetStateAction<string>>;
  handleSearch: (q?: string) => Promise<void>;
  handleEditSave: () => Promise<void>;
  closeModal: () => void;
}

export function EditOntologyDialog({
  editState,
  searchQuery,
  searchResults,
  searching,
  busy,
  setEditState,
  setSearchQuery,
  handleSearch,
  handleEditSave,
  closeModal,
}: EditOntologyDialogProps) {
  return (
    <Dialog.Root open onOpenChange={(open) => !open && closeModal()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40" />
        <Dialog.Content className="fixed left-1/2 top-20 z-50 w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 space-y-4 rounded-lg bg-white p-6 shadow-xl focus:outline-none dark:bg-slate-900">
          <Dialog.Title className="text-sm font-semibold text-slate-800 dark:text-slate-200">Set ontology term</Dialog.Title>
          <Dialog.Description className="sr-only">
            Assign a controlled-vocabulary term and ontology identifier to this value.
          </Dialog.Description>
          {editState.raw && (
            <p className="text-xs text-slate-500">
              Assigning a term to <code className="rounded bg-slate-100 dark:bg-slate-800/70 px-1.5 py-0.5 text-slate-700 dark:text-slate-300">{editState.raw}</code>
            </p>
          )}
          <div className="space-y-2">
            <label className="text-xs text-slate-500">Term name</label>
            <input
              autoFocus
              value={editState.term}
              onChange={(e) => setEditState({ ...editState, term: e.target.value })}
              onKeyDown={(e) => e.key === 'Enter' && handleEditSave()}
              placeholder="e.g. Male"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs text-slate-500">Ontology ID (optional — auto-resolved if blank)</label>
            <input
              value={editState.ontId}
              onChange={(e) => setEditState({ ...editState, ontId: e.target.value })}
              placeholder="e.g. NCIT:C20197"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            />
          </div>

          {/* Search panel */}
          <div className="rounded-lg border border-slate-100 bg-slate-50/60 p-3 dark:border-slate-800 dark:bg-slate-800/40">
            <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-slate-600 dark:text-slate-300">
              <Search className="h-3.5 w-3.5" />
              Ontology suggestions
            </div>
            <div className="flex gap-2">
              <input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="Search NCIT, UBERON…"
                className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              />
              <button type="button" aria-label="Search ontology" onClick={() => handleSearch()} disabled={searching} className="rounded-lg bg-primary-600 p-2 text-white hover:bg-primary-700">
                {searching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
              </button>
            </div>
            {searching && searchResults.length === 0 && (
              <p className="mt-2 text-xs text-slate-400">Searching…</p>
            )}
            {!searching && searchQuery && searchResults.length === 0 && (
              <p className="mt-2 text-xs text-slate-400">No matches — type a different term above.</p>
            )}
            {searchResults.length > 0 && (
              <ul className="mt-3 max-h-56 space-y-2 overflow-y-auto">
                {searchResults.map((r, i) => (
                  <li
                    key={`${r.ontology_id}-${i}`}
                    onClick={() => setEditState({ ...editState, term: r.term, ontId: r.ontology_id })}
                    className="cursor-pointer rounded-lg border border-slate-100 bg-white p-2 text-xs hover:border-primary-300 hover:bg-primary-50 dark:border-slate-800 dark:bg-slate-900 dark:hover:border-primary-500/50 dark:hover:bg-primary-500/10"
                  >
                    <div className="font-medium text-slate-900 dark:text-slate-100">{r.term}</div>
                    <div className="mt-0.5 flex items-center gap-2">
                      {r.ontology_id === 'NCIT:unknown' ? (
                        <span className="italic text-slate-400 dark:text-slate-500">dictionary term · no ontology code</span>
                      ) : (
                        <>
                          <span className="font-mono text-slate-500 dark:text-slate-400">{r.ontology_id}</span>
                          <span className="text-slate-400 dark:text-slate-500">{r.ontology}</span>
                        </>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="flex justify-end gap-2">
            <button type="button" onClick={closeModal} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800">
              Cancel
            </button>
            <button
              type="button"
              disabled={!editState.term.trim() || busy[editState.id]}
              onClick={handleEditSave}
              className="flex items-center gap-1 rounded-lg bg-primary-600 px-3 py-1.5 text-sm text-white hover:bg-primary-700 disabled:opacity-50"
            >
              {busy[editState.id] ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Save'}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
