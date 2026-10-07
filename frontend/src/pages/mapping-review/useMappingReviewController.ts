import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { useStudies, useServerConfig } from '../../hooks/queries';
import {
  getStudyMappings,
  acceptMapping,
  rejectMapping,
  editMapping,
  batchUpdateMappings,
  llmRematch,
  getReviewQueue,
} from '../../api/client';
import { ApiError } from '../../api/http';
import type { Mapping } from '../../api/types';
import {
  defaultMappingStatusFilter,
  nextMappingSortMode,
  sortMappings,
  sortMappingsBySmartRank,
  type MappingSortMode,
} from '../../lib/mappingFilters';
import type { FilterStage, FilterStatus, GroupInfo, LlmSuggestion, QueueStats, SortKey } from './types';

export function useMappingReviewController() {
  const { studyId } = useParams<{ studyId: string }>();
  const { data: studies, isLoading: studiesLoading } = useStudies();

  const [mappings, setMappings] = useState<Mapping[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(studyId ?? null);
  const [expandedRow, setExpandedRow] = useState<number | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const [searchParams] = useSearchParams();
  const requestedStatus = searchParams.get('status') as FilterStatus | null;
  const initialStatus = requestedStatus || 'pending';
  const initialStage = (searchParams.get('stage') as FilterStage) || 'all';
  const [filterStage, setFilterStage] = useState<FilterStage>(initialStage);
  const [filterStatus, setFilterStatus] = useState<FilterStatus>(initialStatus);
  const [sortKey, setSortKey] = useState<SortKey>('confidence_score');
  const [sortMode, setSortMode] = useState<MappingSortMode>('smart');
  const [search, setSearch] = useState('');

  const smartOrder = true;
  const [groupInfo, setGroupInfo] = useState<GroupInfo>({});
  const [queueStats, setQueueStats] = useState<QueueStats | null>(null);

  const [cursor, setCursor] = useState(0);
  const searchRef = useRef<HTMLInputElement>(null);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editField, setEditField] = useState('');
  const [editNote, setEditNote] = useState('');

  useEffect(() => {
    setSelectedId(studyId ?? null);
  }, [studyId]);

  useEffect(() => {
    if (!selectedId) return;
    setLoading(true);
    getStudyMappings(selectedId)
      .then((fresh) => {
        setMappings(fresh);
        setFilterStatus(defaultMappingStatusFilter(fresh, requestedStatus));
      })
      .catch((error) => {
        setMappings([]);
        toast.error(error instanceof ApiError ? error.message : 'Failed to load schema mappings.');
      })
      .finally(() => setLoading(false));
  }, [requestedStatus, selectedId]);

  useEffect(() => {
    if (!selectedId || !smartOrder) {
      setGroupInfo({});
      setQueueStats(null);
      return;
    }
    getReviewQueue(selectedId)
      .then((q) => {
        const info: GroupInfo = {};
        q.items.forEach((it, index) => {
          info[it.id] = {
            key: it.group_key,
            size: it.group_size,
            min: it.group_min_confidence,
            rank: index, // the server's active-learning order (stable risky-first)
          };
        });
        setGroupInfo(info);
        setQueueStats(q.stats);
      })
      .catch((error) => {
        setGroupInfo({});
        setQueueStats(null);
        toast.error(error instanceof ApiError ? error.message : 'Failed to load smart review order.');
      });
  }, [selectedId, smartOrder, mappings]);

  const showToast = (message: string, type: 'success' | 'error' = 'success') =>
    type === 'success' ? toast.success(message) : toast.error(message);

  const remember = true;

  const filteredMappings = useMemo(() => {
    let result = [...mappings];
    if (filterStage !== 'all') result = result.filter((m) => m.stage === filterStage);
    if (filterStatus !== 'all') result = result.filter((m) => m.status === filterStatus);
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      result = result.filter(
        (m) =>
          m.raw_column.toLowerCase().includes(q) ||
          (m.curator_field || m.matched_field || '').toLowerCase().includes(q),
      );
    }
    if (sortMode === 'smart') {
      return sortMappingsBySmartRank(
        result,
        Object.fromEntries(Object.entries(groupInfo).map(([id, info]) => [id, info.rank])),
      );
    }
    return sortMappings(result, sortKey, sortMode === 'ascending');
  }, [mappings, filterStage, filterStatus, sortKey, sortMode, search, groupInfo]);

  const stageCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const m of mappings) {
      const key = m.stage ?? 'unmapped';
      counts[key] = (counts[key] ?? 0) + 1;
    }
    return counts;
  }, [mappings]);

  const reviewedCount = useMemo(
    () => mappings.filter((m) => m.status === 'accepted' || m.status === 'rejected').length,
    [mappings],
  );

  const selectedGroups = useMemo(() => {
    const byKey = new Map<string, number[]>();
    for (const m of filteredMappings) {
      if (m.status !== 'pending') continue;
      const k = groupInfo[m.id]?.key;
      if (!k) continue;
      const arr = byKey.get(k) ?? [];
      arr.push(m.id);
      byKey.set(k, arr);
    }
    const full = new Set<string>();
    byKey.forEach((ids, k) => {
      if (ids.length > 1 && ids.every((id) => selected.has(id))) full.add(k);
    });
    return full;
  }, [filteredMappings, groupInfo, selected]);

  const updateMapping = useCallback(
    (updated: Mapping) => {
      setMappings((prev) => prev.map((m) => (m.id === updated.id ? updated : m)));
    },
    [],
  );

  const handleAccept = async (id: number) => {
    try {
      const m = await acceptMapping(id, remember);
      updateMapping(m);
    } catch {
      showToast('Failed to accept mapping', 'error');
    }
  };
  const handleReject = async (id: number) => {
    try {
      const m = await rejectMapping(id, remember);
      updateMapping(m);
    } catch {
      showToast('Failed to reject mapping', 'error');
    }
  };
  const handleEditSubmit = async () => {
    if (editingId === null) return;
    try {
      const m = await editMapping(editingId, editField, editNote, remember);
      updateMapping(m);
    } catch {
      showToast('Failed to edit mapping', 'error');
    }
    closeEdit();
  };

  const handleApplyAlternative = async (id: number, field: string) => {
    try {
      const m = await editMapping(id, field, 'Applied alternative suggestion', remember);
      updateMapping(m);
    } catch {
      showToast('Failed to apply alternative', 'error');
    }
  };

  const { data: serverConfig } = useServerConfig();
  const llmEnabled = serverConfig?.llm_enabled ?? false;

  const [llmBusyId, setLlmBusyId] = useState<number | null>(null);
  const [llmResults, setLlmResults] = useState<Record<number, LlmSuggestion[]>>({});
  const handleLlmRematch = async (id: number) => {
    setLlmBusyId(id);
    try {
      const suggestions = await llmRematch(id);
      setLlmResults((prev) => ({ ...prev, [id]: suggestions }));
      setExpandedRow(id);
    } catch (err) {
      const msg =
        err instanceof ApiError && err.status === 503
          ? 'LLM matching is not configured on the server (set GEMINI_API_KEY).'
          : 'LLM rematch failed. Please try again.';
      showToast(msg, 'error');
    } finally {
      setLlmBusyId(null);
    }
  };

  const handleBatch = async (action: 'accepted' | 'rejected') => {
    if (selected.size === 0) return;
    try {
      await batchUpdateMappings([...selected], action, remember);
      if (selectedId) {
        const fresh = await getStudyMappings(selectedId);
        setMappings(fresh);
      }
    } catch {
      showToast('Batch update failed', 'error');
    }
    setSelected(new Set());
  };

  const toggleSelect = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };
  const toggleSelectAll = () => {
    if (selected.size === filteredMappings.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(filteredMappings.map((m) => m.id)));
    }
  };

  const selectGroup = (groupKey: string) => {
    const ids = filteredMappings
      .filter((m) => m.status === 'pending' && groupInfo[m.id]?.key === groupKey)
      .map((m) => m.id);
    if (ids.length === 0) return;
    setSelected((prev) => {
      const allSelected = ids.every((id) => prev.has(id));
      const next = new Set(prev);
      ids.forEach((id) => (allSelected ? next.delete(id) : next.add(id)));
      return next;
    });
  };

  const toggleSort = (key: SortKey) => {
    setSortMode(nextMappingSortMode(sortMode, sortKey === key));
    setSortKey(key);
  };

  const openEdit = (m: Mapping) => {
    setEditingId(m.id);
    setEditField(m.curator_field || m.matched_field || '');
    setEditNote('');
  };

  const closeEdit = () => {
    setEditingId(null);
    setEditField('');
    setEditNote('');
  };

  const handleStatusFilterChange = (status: FilterStatus) => {
    setFilterStatus(status);
    setSelected(new Set());
  };

  useEffect(() => {
    setCursor((c) => Math.min(Math.max(0, c), Math.max(0, filteredMappings.length - 1)));
  }, [filteredMappings.length]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      const typing = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
      if (e.key === '/' && !typing) {
        e.preventDefault();
        searchRef.current?.focus();
        return;
      }
      if (typing || editingId !== null) return;
      const list = filteredMappings;
      if (!list.length) return;
      const cur = list[Math.min(cursor, list.length - 1)];
      switch (e.key) {
        case 'j':
          e.preventDefault();
          setCursor((c) => Math.min(c + 1, list.length - 1));
          break;
        case 'k':
          e.preventDefault();
          setCursor((c) => Math.max(c - 1, 0));
          break;
        case 'a':
          if (cur && cur.status !== 'accepted') { e.preventDefault(); handleAccept(cur.id); }
          break;
        case 'r':
          if (cur && cur.status !== 'rejected') { e.preventDefault(); handleReject(cur.id); }
          break;
        case 'e':
          if (cur) { e.preventDefault(); openEdit(cur); }
          break;
        case 'x':
          if (cur) { e.preventDefault(); toggleSelect(cur.id); }
          break;
        case 'Enter':
          if (cur) { e.preventDefault(); setExpandedRow((r) => (r === cur.id ? null : cur.id)); }
          break;
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [filteredMappings, cursor, editingId]);

  useEffect(() => {
    const el = document.querySelector(`[data-row-cursor="true"]`);
    el?.scrollIntoView({ block: 'nearest' });
  }, [cursor]);

  const selectedStudy = studies?.find((s) => s.id === selectedId);

  return {
    studies,
    studiesLoading,
    mappings,
    loading,
    selectedId,
    expandedRow,
    selected,
    filterStage,
    filterStatus,
    sortKey,
    sortMode,
    search,
    smartOrder,
    groupInfo,
    queueStats,
    cursor,
    searchRef,
    editingId,
    editField,
    editNote,
    filteredMappings,
    stageCounts,
    reviewedCount,
    selectedGroups,
    selectedStudy,
    llmEnabled,
    llmBusyId,
    llmResults,
    setFilterStage,
    setSearch,
    setCursor,
    setExpandedRow,
    setEditField,
    setEditNote,
    handleAccept,
    handleReject,
    handleEditSubmit,
    handleApplyAlternative,
    handleLlmRematch,
    handleBatch,
    toggleSelect,
    toggleSelectAll,
    selectGroup,
    toggleSort,
    openEdit,
    closeEdit,
    handleStatusFilterChange,
  };
}
