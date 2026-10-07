import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { toast } from 'sonner';
import {
  acceptOntologyMapping,
  editOntologyMapping,
  getOntologyMappings,
  rejectOntologyMapping,
  searchOntology,
  suggestOntologyTerms,
} from '../../api/client';
import { ApiError } from '../../api/http';
import type { OntologyMapping, OntologySearchResult } from '../../api/types';
import { useStudies } from '../../hooks/queries';
import type {
  EditState,
  OntologyStats,
  OntologySuggestion,
  RewritePreviewRow,
  StatusFilter,
  UnmatchedGroupItem,
} from './types';
import { hasTerm } from './utils';

export function useOntologyReviewState() {
  const { studyId } = useParams<{ studyId: string }>();
  const { data: studies, isLoading: studiesLoading } = useStudies();

  const [selectedId, setSelectedId] = useState<string | null>(studyId ?? null);
  const [ontoMappings, setOntoMappings] = useState<OntologyMapping[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState<Record<number, boolean>>({});
  const [editState, setEditState] = useState<EditState | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [showUnmatched, setShowUnmatched] = useState(false);
  const [showAllSuggestions, setShowAllSuggestions] = useState(false);
  // Live "what the export will write" preview — before→after per field.
  const [showPreview, setShowPreview] = useState(false);
  // Per-field "show all unmatched values" toggle.
  const [expandedFields, setExpandedFields] = useState<Record<string, boolean>>({});

  // Search (lives inside the edit modal)
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<OntologySearchResult[]>([]);
  const [searching, setSearching] = useState(false);

  // Auto-suggestions for unmatched values (ontology-index lookup, batched).
  // Keyed by mapping id → the best candidate term/id/score found.
  const [suggestions, setSuggestions] = useState<Record<number, OntologySuggestion>>({});
  const [finding, setFinding] = useState(false);

  useEffect(() => {
    setSelectedId(studyId ?? null);
  }, [studyId]);

  useEffect(() => {
    if (!selectedId) return;
    setLoading(true);
    getOntologyMappings(selectedId)
      .then(setOntoMappings)
      .catch((error) => {
        setOntoMappings([]);
        toast.error(error instanceof ApiError ? error.message : 'Failed to load ontology mappings.');
      })
      .finally(() => setLoading(false));
  }, [selectedId]);

  const patch = (updated: OntologyMapping) =>
    setOntoMappings((prev) => prev.map((m) => (m.id === updated.id ? updated : m)));

  const remember = true;

  const handleAccept = async (id: number) => {
    setBusy((b) => ({ ...b, [id]: true }));
    try { patch(await acceptOntologyMapping(id, remember)); } catch { toast.error('Could not accept the ontology mapping.'); }
    finally { setBusy((b) => ({ ...b, [id]: false })); }
  };

  const handleReject = async (id: number) => {
    setBusy((b) => ({ ...b, [id]: true }));
    try { patch(await rejectOntologyMapping(id, remember)); } catch { toast.error('Could not reject the ontology mapping.'); }
    finally { setBusy((b) => ({ ...b, [id]: false })); }
  };

  const handleEditSave = async () => {
    if (!editState || !editState.term.trim()) return;
    const term = editState.term.trim();
    const ontId = editState.ontId.trim();
    // Apply the curator's term to every row that shares this value within the
    // same field — both already-matched and unmatched occurrences — so a manual
    // assignment fixes all of them at once (consistent with the suggestions
    // panel) and the value won't linger in the unmatched list.
    const targetRow = ontoMappings.find((m) => m.id === editState.id);
    const key = targetRow?.raw_value.trim().toLowerCase();
    const ids = targetRow
      ? ontoMappings
          .filter((m) => m.raw_value.trim().toLowerCase() === key && m.field_name === targetRow.field_name)
          .map((m) => m.id)
      : [editState.id];
    setBusy((b) => {
      const nb = { ...b };
      ids.forEach((id) => (nb[id] = true));
      return nb;
    });
    try {
      // All ids share the same (field, value) → same learned-decision key, so
      // only remember once (idx 0) to avoid inflating the support_count.
      const updated = await Promise.all(
        ids.map((id, idx) => editOntologyMapping(id, term, ontId, remember && idx === 0)),
      );
      updated.forEach(patch);
      // Clear any suggestion entries for these rows.
      setSuggestions((prev) => {
        const rest = { ...prev };
        ids.forEach((id) => delete rest[id]);
        return rest;
      });
      toast.success(`Applied ${term}${ids.length > 1 ? ` to ${ids.length} values` : ''}`);
      setEditState(null);
      setSearchResults([]);
      setSearchQuery('');
    } catch {
      toast.error('Could not save the term.');
    } finally {
      setBusy((b) => {
        const nb = { ...b };
        ids.forEach((id) => (nb[id] = false));
        return nb;
      });
    }
  };

  const handleSearch = async (q?: string) => {
    const query = (q ?? searchQuery).trim();
    if (!query) return;
    setSearching(true);
    try { setSearchResults(await searchOntology(query)); }
    catch {
      setSearchResults([]);
      toast.error('Ontology search failed.');
    }
    finally { setSearching(false); }
  };

  // When the assign/edit modal opens for an unmatched value, auto-search the
  // raw value so the curator immediately sees ontology candidates (the matcher
  // is field-scoped, so a value can lack a match for its column yet still exist
  // in another field — surfacing it here turns a manual lookup into one click).
  useEffect(() => {
    if (editState && !editState.term && editState.raw) {
      setSearchQuery(editState.raw);
    }
    // Only re-run when a different mapping is opened.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editState?.id]);

  useEffect(() => {
    if (!editState) return;
    const q = searchQuery.trim();
    if (!q) {
      setSearchResults([]);
      return;
    }
    const t = setTimeout(() => void handleSearch(q), 250);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchQuery, editState?.id]);

  const closeModal = () => {
    setEditState(null);
    setSearchResults([]);
    setSearchQuery('');
  };

  // ── Split matched (has a candidate ontology term — actionable) from
  //    unmatched (free-text / identifiers with no ontology equivalent — noise).
  const { matched, unmatched } = useMemo(() => {
    const m: OntologyMapping[] = [];
    const u: OntologyMapping[] = [];
    for (const om of ontoMappings) (hasTerm(om) ? m : u).push(om);
    return { matched: m, unmatched: u };
  }, [ontoMappings]);

  const stats: OntologyStats = useMemo(() => ({
    mapped: matched.length,
    accepted: matched.filter((m) => m.status === 'accepted').length,
    pending: matched.filter((m) => m.status === 'pending').length,
    unmatched: unmatched.length,
  }), [matched, unmatched]);

  // Live export preview: the value rewrites that will be applied on export —
  // exactly the accepted `raw_value -> confirmed term` per field. Recomputes
  // instantly as the curator accepts/edits, so they see the effect before
  // exporting (the raw upload itself is never mutated).
  const rewritePreview: Record<string, RewritePreviewRow[]> = useMemo(() => {
    const byField: Record<string, RewritePreviewRow[]> = {};
    for (const m of matched) {
      if (m.status !== 'accepted') continue;
      const term = m.curator_term ?? m.ontology_term;
      if (!term) continue;
      (byField[m.field_name] ??= []).push({
        raw: m.raw_value,
        term,
        ontId: m.curator_id ?? m.ontology_id ?? null,
      });
    }
    return byField;
  }, [matched]);
  const previewFieldCount = Object.keys(rewritePreview).length;
  const previewValueCount = Object.values(rewritePreview).reduce((n, v) => n + v.length, 0);

  // Ask the backend to search the ontology index for every unmatched value
  //  and return high-confidence candidates — a single request (the server does
  //  the fuzzy matching), so no per-value HTTP fan-out / rate-limit storm.
  const findSuggestions = async () => {
    if (!selectedId) return;
    setFinding(true);
    try {
      const raw = await suggestOntologyTerms(selectedId);
      const next: Record<number, OntologySuggestion> = {};
      for (const [id, s] of Object.entries(raw)) {
        next[Number(id)] = { term: s.term, ontId: s.ontology_id, score: s.score };
      }
      setSuggestions(next);
      const n = Object.keys(next).length;
      if (n === 0) toast('No confident ontology suggestions found.');
      else {
        setShowUnmatched(true);
        toast.success(`Found ${n} suggested ${n === 1 ? 'match' : 'matches'} to review.`);
      }
    } catch {
      toast.error('Could not fetch suggestions.');
    } finally {
      setFinding(false);
    }
  };

  const applySuggestion = async (m: OntologyMapping) => {
    const s = suggestions[m.id];
    if (!s) return;
    // Apply to EVERY unmatched row that shares this raw value (in the same
    // field) so a deduplicated suggestion clears all its occurrences at once —
    // otherwise the value would reappear in the unmatched list.
    const key = m.raw_value.trim().toLowerCase();
    const targets = unmatched.filter(
      (u) => u.raw_value.trim().toLowerCase() === key && u.field_name === m.field_name && suggestions[u.id],
    );
    const ids = targets.length ? targets : [m];
    setBusy((b) => {
      const nb = { ...b };
      ids.forEach((t) => (nb[t.id] = true));
      return nb;
    });
    try {
      const updated = await Promise.all(ids.map((t) => editOntologyMapping(t.id, s.term, s.ontId)));
      updated.forEach(patch);
      setSuggestions((prev) => {
        const rest = { ...prev };
        ids.forEach((t) => delete rest[t.id]);
        return rest;
      });
      toast.success(
        `Applied ${s.term}${ids.length > 1 ? ` to ${ids.length} values` : ''}`,
      );
    } catch {
      toast.error('Could not apply the term.');
    } finally {
      setBusy((b) => {
        const nb = { ...b };
        ids.forEach((t) => (nb[t.id] = false));
        return nb;
      });
    }
  };

  const dismissSuggestion = (m: OntologyMapping) => {
    // Dismiss every row sharing this value so the de-duplicated card vanishes.
    const key = m.raw_value.trim().toLowerCase();
    setSuggestions((prev) => {
      const rest = { ...prev };
      for (const u of unmatched) {
        if (u.raw_value.trim().toLowerCase() === key && u.field_name === m.field_name) {
          delete rest[u.id];
        }
      }
      return rest;
    });
  };

  // Matched, filtered by status, grouped by field.
  const groupedMatched = useMemo(() => {
    const rows = statusFilter === 'all' ? matched : matched.filter((m) => m.status === statusFilter);
    const g: Record<string, OntologyMapping[]> = {};
    for (const m of rows) (g[m.field_name] ??= []).push(m);
    return g;
  }, [matched, statusFilter]);

  // Unmatched grouped by field, de-duplicated by value (so a value repeated
  // across many rows shows once, with an occurrence count). Sorted by frequency.
  const groupedUnmatched = useMemo(() => {
    const g: Record<string, UnmatchedGroupItem[]> = {};
    const idx: Record<string, Map<string, UnmatchedGroupItem>> = {};
    for (const m of unmatched) {
      const field = m.field_name;
      const key = m.raw_value.trim().toLowerCase();
      (idx[field] ??= new Map());
      const existing = idx[field].get(key);
      if (existing) existing.count += 1;
      else idx[field].set(key, { row: m, count: 1 });
    }
    for (const [field, map] of Object.entries(idx)) {
      g[field] = Array.from(map.values()).sort((a, b) => b.count - a.count);
    }
    return g;
  }, [unmatched]);

  // Unmatched rows that picked up an ontology suggestion, de-duplicated by
  // (value, field) so the same value isn't listed many times. The kept row
  // also carries how many occurrences applying it will resolve.
  const suggestedRows = useMemo(() => {
    const seen = new Set<string>();
    const out: UnmatchedGroupItem[] = [];
    const counts = new Map<string, number>();
    for (const m of unmatched) {
      if (!suggestions[m.id]) continue;
      const k = `${m.field_name}::${m.raw_value.trim().toLowerCase()}`;
      counts.set(k, (counts.get(k) ?? 0) + 1);
    }
    for (const m of unmatched) {
      if (!suggestions[m.id]) continue;
      const k = `${m.field_name}::${m.raw_value.trim().toLowerCase()}`;
      if (seen.has(k)) continue;
      seen.add(k);
      out.push({ row: m, count: counts.get(k) ?? 1 });
    }
    // Highest-confidence first.
    out.sort((a, b) => (suggestions[b.row.id]?.score ?? 0) - (suggestions[a.row.id]?.score ?? 0));
    return out;
  }, [unmatched, suggestions]);

  const selectedStudy = studies?.find((s) => s.id === selectedId);
  const matchedFields = Object.keys(groupedMatched);

  return {
    selectedId,
    studies,
    studiesLoading,
    selectedStudy,
    loading,
    busy,
    editState,
    setEditState,
    statusFilter,
    setStatusFilter,
    showUnmatched,
    setShowUnmatched,
    showAllSuggestions,
    setShowAllSuggestions,
    showPreview,
    setShowPreview,
    expandedFields,
    setExpandedFields,
    searchQuery,
    setSearchQuery,
    searchResults,
    searching,
    suggestions,
    finding,
    matched,
    stats,
    rewritePreview,
    previewFieldCount,
    previewValueCount,
    handleAccept,
    handleReject,
    handleEditSave,
    handleSearch,
    closeModal,
    findSuggestions,
    applySuggestion,
    dismissSuggestion,
    groupedMatched,
    groupedUnmatched,
    suggestedRows,
    matchedFields,
  };
}
