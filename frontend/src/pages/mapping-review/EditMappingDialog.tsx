import * as Dialog from '@radix-ui/react-dialog';

type EditMappingDialogProps = {
  editingId: number | null;
  editField: string;
  editNote: string;
  onEditFieldChange: (field: string) => void;
  onEditNoteChange: (note: string) => void;
  onCancel: () => void;
  onSubmit: () => void;
};

export function EditMappingDialog({
  editingId,
  editField,
  editNote,
  onEditFieldChange,
  onEditNoteChange,
  onCancel,
  onSubmit,
}: EditMappingDialogProps) {
  return (
    <Dialog.Root
      open={editingId !== null}
      onOpenChange={(open) => {
        if (!open) {
          onCancel();
        }
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-20 z-50 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 space-y-4 rounded-lg border border-slate-200 bg-white p-6 shadow-pop focus:outline-none dark:border-slate-800 dark:bg-slate-900">
          <Dialog.Title className="text-lg font-semibold text-slate-900 dark:text-slate-100">Edit mapping</Dialog.Title>
          <Dialog.Description className="text-sm text-slate-500 dark:text-slate-400">
            Replace the proposed target field and optionally record why.
          </Dialog.Description>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
              New field name
            </label>
            <input
              value={editField}
              onChange={(e) => onEditFieldChange(e.target.value)}
              className="field"
              placeholder="e.g. sex, age_years, body_site"
              autoFocus
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
              Note (optional)
            </label>
            <textarea
              value={editNote}
              onChange={(e) => onEditNoteChange(e.target.value)}
              className="field"
              rows={2}
            />
          </div>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onCancel}
              className="btn-secondary btn-sm"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={onSubmit}
              disabled={!editField.trim()}
              className="btn-primary btn-sm"
            >
              Save
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
