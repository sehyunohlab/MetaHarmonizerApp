import { Table2 } from 'lucide-react';
import StudyPicker from '../components/StudyPicker';
import StudyGate, { isStudyReady } from '../components/StudyGate';
import { EditMappingDialog } from './mapping-review/EditMappingDialog';
import { KeyboardHint } from './mapping-review/KeyboardHint';
import { MappingFilters } from './mapping-review/MappingFilters';
import { MappingReviewHeader } from './mapping-review/MappingReviewHeader';
import { MappingStatusFilter } from './mapping-review/MappingStatusFilter';
import { MappingTable } from './mapping-review/MappingTable';
import { StageBreakdown } from './mapping-review/StageBreakdown';
import { useMappingReviewController } from './mapping-review/useMappingReviewController';

export default function MappingReview() {
  const review = useMappingReviewController();

  // No study selected
  if (!review.selectedId) {
    return (
      <StudyPicker
        title="Mapping review"
        description="Pick a study to review and curate column mappings."
        icon={<Table2 className="h-6 w-6" />}
        studies={review.studies}
        loading={review.studiesLoading}
        basePath="/review"
      />
    );
  }

  // Study selected but not yet harmonized → show a readiness gate instead of an
  // empty table (auto-resolves to the real page once processing completes).
  if (review.selectedStudy && !isStudyReady(review.selectedStudy.status)) {
    return <StudyGate study={review.selectedStudy} title="Mapping review" icon={<Table2 className="h-6 w-6" />} />;
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <MappingReviewHeader
        mappingsCount={review.mappings.length}
        reviewedCount={review.reviewedCount}
        selectedCount={review.selected.size}
        onBatch={review.handleBatch}
      />

      {/* Status filter */}
      <MappingStatusFilter
        filterStatus={review.filterStatus}
        mappings={review.mappings}
        onChange={review.handleStatusFilterChange}
      />

      {/* Stage distribution — at-a-glance breakdown, click a segment to filter */}
      <StageBreakdown
        filterStage={review.filterStage}
        mappingsCount={review.mappings.length}
        stageCounts={review.stageCounts}
        onFilterStageChange={review.setFilterStage}
      />

      {/* Filters */}
      <MappingFilters
        filterStage={review.filterStage}
        search={review.search}
        searchRef={review.searchRef}
        llmEnabled={review.llmEnabled}
        queueStats={review.queueStats}
        sortMode={review.sortMode}
        filteredCount={review.filteredMappings.length}
        mappingsCount={review.mappings.length}
        onFilterStageChange={review.setFilterStage}
        onSearchChange={review.setSearch}
      />

      {/* Keyboard hint */}
      <KeyboardHint />

      {/* Table */}
      <MappingTable
        loading={review.loading}
        filteredMappings={review.filteredMappings}
        selected={review.selected}
        cursor={review.cursor}
        sortKey={review.sortKey}
        sortMode={review.sortMode}
        smartOrder={review.smartOrder}
        groupInfo={review.groupInfo}
        selectedGroups={review.selectedGroups}
        expandedRow={review.expandedRow}
        selectedId={review.selectedId}
        llmEnabled={review.llmEnabled}
        llmBusyId={review.llmBusyId}
        llmResults={review.llmResults}
        onToggleSelectAll={review.toggleSelectAll}
        onToggleSelect={review.toggleSelect}
        onSelectGroup={review.selectGroup}
        onSort={review.toggleSort}
        onCursorChange={review.setCursor}
        onAccept={review.handleAccept}
        onReject={review.handleReject}
        onOpenEdit={review.openEdit}
        onExpandedRowChange={review.setExpandedRow}
        onApplyAlternative={review.handleApplyAlternative}
        onLlmRematch={review.handleLlmRematch}
      />

      {/* Edit Modal */}
      <EditMappingDialog
        editingId={review.editingId}
        editField={review.editField}
        editNote={review.editNote}
        onEditFieldChange={review.setEditField}
        onEditNoteChange={review.setEditNote}
        onCancel={review.closeEdit}
        onSubmit={review.handleEditSubmit}
      />
    </div>
  );
}
