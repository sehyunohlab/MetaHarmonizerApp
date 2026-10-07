import { Loader2 } from 'lucide-react';
import PageHeader from '../components/ui/PageHeader';
import OntologyIcon from '../components/icons/OntologyIcon';
import StudyPicker from '../components/StudyPicker';
import StudyGate, { isStudyReady } from '../components/StudyGate';
import { Card, CardBody } from '../components/ui/Card';
import { EditOntologyDialog } from './ontology-review/EditOntologyDialog';
import { MatchedMappingsList } from './ontology-review/MatchedMappingsList';
import { ResolvedValuesPreview } from './ontology-review/ResolvedValuesPreview';
import { StatusFilterControl } from './ontology-review/StatusFilterControl';
import { SummaryCards } from './ontology-review/SummaryCards';
import { UnmatchedMappingsCard } from './ontology-review/UnmatchedMappingsCard';
import { useOntologyReviewState } from './ontology-review/useOntologyReviewState';

export default function OntologyReview() {
  const {
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
  } = useOntologyReviewState();

  if (!selectedId) {
    return (
      <StudyPicker
        title="Ontology review"
        description="Pick a study to review and curate ontology value mappings."
        icon={<OntologyIcon className="h-6 w-6" />}
        studies={studies}
        loading={studiesLoading}
        basePath="/ontology"
      />
    );
  }

  if (selectedStudy && !isStudyReady(selectedStudy.status)) {
    return <StudyGate study={selectedStudy} title="Ontology review" icon={<OntologyIcon className="h-6 w-6" />} />;
  }

  return (
    <div className="space-y-6">
      {/* Edit Modal (with embedded search) */}
      {editState && (
        <EditOntologyDialog
          editState={editState}
          searchQuery={searchQuery}
          searchResults={searchResults}
          searching={searching}
          busy={busy}
          setEditState={setEditState}
          setSearchQuery={setSearchQuery}
          handleSearch={handleSearch}
          handleEditSave={handleEditSave}
          closeModal={closeModal}
        />
      )}

      <PageHeader
        title="Ontology review"
        description="Curate the controlled-vocabulary terms the engine assigned to each categorical value."
        icon={<OntologyIcon className="h-6 w-6" />}
      />

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-primary-500" />
        </div>
      ) : (
        <>
          {/* Summary */}
          <SummaryCards stats={stats} />

          {stats.mapped === 0 ? (
            <Card>
              <CardBody className="py-12 text-center text-slate-400">
                No values in this study mapped to an ontology term.
              </CardBody>
            </Card>
          ) : (
            <>
              {/* Live export preview — before → after of accepted rewrites */}
              <ResolvedValuesPreview
                showPreview={showPreview}
                setShowPreview={setShowPreview}
                rewritePreview={rewritePreview}
                previewFieldCount={previewFieldCount}
                previewValueCount={previewValueCount}
              />

              {/* Status filter */}
              <StatusFilterControl
                statusFilter={statusFilter}
                setStatusFilter={setStatusFilter}
                matched={matched}
              />

              {/* Matched, grouped by field */}
              <MatchedMappingsList
                matchedFields={matchedFields}
                groupedMatched={groupedMatched}
                busy={busy}
                statusFilter={statusFilter}
                handleAccept={handleAccept}
                handleReject={handleReject}
                setEditState={setEditState}
              />
            </>
          )}

          {/* Unmatched — collapsed explainer (free-text / identifiers) */}
          <UnmatchedMappingsCard
            stats={stats}
            showUnmatched={showUnmatched}
            setShowUnmatched={setShowUnmatched}
            finding={finding}
            findSuggestions={findSuggestions}
            suggestedRows={suggestedRows}
            showAllSuggestions={showAllSuggestions}
            setShowAllSuggestions={setShowAllSuggestions}
            suggestions={suggestions}
            busy={busy}
            applySuggestion={applySuggestion}
            dismissSuggestion={dismissSuggestion}
            setEditState={setEditState}
            groupedUnmatched={groupedUnmatched}
            expandedFields={expandedFields}
            setExpandedFields={setExpandedFields}
          />
        </>
      )}
    </div>
  );
}
