/*
 * Guest-preview sample data.
 *
 * In the no-account preview we never hit the backend (see http.ts). To let a
 * visitor see what a *curated* study actually looks like, apiFetch serves these
 * fixtures for GET requests while in guest mode. Numbers mirror a real
 * CPTAC -> GDC harmonization so the walkthrough feels authentic.
 *
 * Only types are imported here (no runtime deps) to avoid an import cycle with
 * the HTTP layer.
 */
import type {
    ExportColumnChange,
    ExportPreview,
    Mapping,
    OntologyMapping,
    QualityMetrics,
    Study,
} from './types';

export const DEMO_STUDY_ID = 'DEMO-CPTAC';

const REVIEWED = '2026-07-12T10:00:00Z';

const demoStudy: Study = {
    id: DEMO_STUDY_ID,
    name: 'CPTAC Endometrial Carcinoma (preview)',
    upload_date: '2026-07-12T09:00:00Z',
    status: 'completed',
    row_count: 153,
    column_count: 24,
};

const m = (
    id: number,
    raw_column: string,
    matched_field: string | null,
    confidence_score: number,
    stage: string,
    status: string,
    alternatives: { field: string; score: number }[] = [],
): Mapping => ({
    id,
    study_id: DEMO_STUDY_ID,
    raw_column,
    matched_field,
    confidence_score,
    stage,
    method: stage === 'stage1' ? 'dictionary' : stage === 'stage2' ? 'sentence-transformer' : 'type-inference',
    alternatives,
    status,
    curator_field: null,
    curator_note: null,
    reviewed_at: status === 'pending' ? null : REVIEWED,
    reviewed_by: status === 'pending' ? null : 'Demo Curator',
});

const demoMappings: Mapping[] = [
    m(1, 'tumor_site', 'primary_site', 1.0, 'stage1', 'accepted'),
    m(2, 'Histologic_Type', 'morphology', 1.0, 'stage1', 'accepted'),
    m(3, 'FIGO_stage', 'figo_stage', 1.0, 'stage1', 'accepted'),
    m(4, 'MSI_status', 'msi_status', 1.0, 'stage1', 'accepted'),
    m(5, 'sex', 'gender', 1.0, 'stage1', 'accepted'),
    m(6, 'BMI', 'bmi', 1.0, 'stage1', 'accepted'),
    m(7, 'vital_status', 'vital_status', 1.0, 'stage1', 'accepted'),
    m(8, 'race', 'race', 1.0, 'stage1', 'accepted'),
    m(9, 'Tumor_Stage_Pathological', 'uicc_pathologic_t', 0.96, 'stage1', 'accepted'),
    m(10, 'tobacco_smoking_status', 'tobacco_smoking_status', 1.0, 'stage1', 'accepted'),
    m(11, 'age', 'age_at_diagnosis', 0.88, 'stage2', 'pending', [
        { field: 'age_at_index', score: 0.83 },
        { field: 'days_to_birth', score: 0.61 },
    ]),
    m(12, 'diagnosis', 'primary_diagnosis', 0.82, 'stage2', 'pending', [
        { field: 'morphology', score: 0.74 },
    ]),
    m(13, 'residual_tumor', 'residual_disease', 0.79, 'stage2', 'pending', [
        { field: 'ajcc_pathologic_stage', score: 0.55 },
    ]),
    m(14, 'TMT_channel', null, 0.21, 'stage3', 'pending'),
    m(15, 'peptide_ratio_norm', null, 0.18, 'stage3', 'pending'),
];

const reviewQueueItems = demoMappings
    .filter((x) => x.status === 'pending')
    .map((x) => ({
        ...x,
        group_key: x.matched_field ?? 'unmapped',
        group_size: 1,
        group_min_confidence: x.confidence_score ?? 0,
    }));

const demoReviewQueue = {
    items: reviewQueueItems,
    stats: {
        pending: reviewQueueItems.length,
        groups: reviewQueueItems.length,
        batchable_groups: 0,
        risky: demoMappings.filter((x) => (x.confidence_score ?? 0) < 0.5).length,
    },
};

const o = (
    id: number,
    field_name: string,
    raw_value: string,
    ontology_term: string | null,
    ontology_id: string | null,
    confidence_score: number,
    status: string,
): OntologyMapping => ({
    id,
    study_id: DEMO_STUDY_ID,
    field_name,
    raw_value,
    ontology_term,
    ontology_id,
    confidence_score,
    status,
    curator_term: null,
    curator_id: null,
});

const demoOntology: OntologyMapping[] = [
    o(1, 'disease', 'Endometrial Carcinoma', 'Endometrial Carcinoma', 'NCIT:C7364', 1.0, 'accepted'),
    o(2, 'disease', 'Serous Carcinoma', 'Serous Adenocarcinoma', 'NCIT:C7570', 0.94, 'accepted'),
    o(3, 'disease', 'Endometrioid Adenocarcinoma', 'Endometrioid Adenocarcinoma', 'NCIT:C6287', 1.0, 'accepted'),
    o(4, 'body_site', 'uterus', 'uterus', 'UBERON:0000995', 1.0, 'accepted'),
    o(5, 'body_site', 'endometrium', 'endometrium', 'UBERON:0001295', 1.0, 'accepted'),
    o(6, 'disease', 'Clear Cell Carcinoma', null, null, 0.42, 'pending'),
];

const demoQuality: QualityMetrics = {
    study_id: DEMO_STUDY_ID,
    total_columns: 24,
    mapped_columns: 13,
    unmapped_columns: 11,
    avg_confidence: 0.82,
    auto_accepted: 10,
    pending_review: 5,
    rejected: 0,
    new_field_suggestions: 2,
    stage_breakdown: [
        { stage: 'stage1', count: 10, percentage: 41.7 },
        { stage: 'stage2', count: 3, percentage: 12.5 },
        { stage: 'stage3', count: 2, percentage: 8.3 },
        { stage: 'unmapped', count: 9, percentage: 37.5 },
    ],
    confidence_distribution: [
        { bucket: '0.9–1.0', min_val: 0.9, max_val: 1.0, count: 10 },
        { bucket: '0.7–0.9', min_val: 0.7, max_val: 0.9, count: 3 },
        { bucket: '0.5–0.7', min_val: 0.5, max_val: 0.7, count: 0 },
        { bucket: '< 0.5', min_val: 0, max_val: 0.5, count: 2 },
    ],
};

/* Export preview: the demo study's harmonized CSV vs. its upload. Cell values
 * are generated deterministically from the row number. */

interface DemoExportColumn {
    source: string;
    target: string | null;
    action: ExportColumnChange['action'];
    mapping_status: ExportColumnChange['mapping_status'];
    value: (row: number) => string;
    rewrite?: Record<string, string>;
}

const pick = (options: string[], row: number, salt: number) => options[(row * 7 + salt * 5) % options.length];

const exported = (
    source: string,
    target: string,
    value: DemoExportColumn['value'],
    rewrite?: Record<string, string>,
    mapping_status: DemoExportColumn['mapping_status'] = 'accepted',
): DemoExportColumn => ({
    source,
    target,
    action: source === target ? 'matched' : 'renamed',
    mapping_status,
    value,
    rewrite,
});

const notExported = (source: string, mapping_status: DemoExportColumn['mapping_status']): DemoExportColumn => ({
    source,
    target: null,
    action: 'dropped',
    mapping_status,
    value: (row) => String(row),
});

const demoExportColumns: DemoExportColumn[] = [
    exported('tumor_site', 'primary_site', () => 'Uterus', { Uterus: 'Corpus uteri' }),
    exported('Histologic_Type', 'morphology', (r) => pick(['Endometrioid', 'Endometrioid', 'Serous', 'Clear cell'], r, 1), {
        Endometrioid: 'Endometrioid adenocarcinoma, NOS',
        Serous: 'Serous adenocarcinoma, NOS',
        'Clear cell': 'Clear cell adenocarcinoma, NOS',
    }),
    exported('FIGO_stage', 'figo_stage', (r) => pick(['IA', 'IB', 'II', 'IIIA', 'IIIC1', 'IVB'], r, 2)),
    exported('MSI_status', 'msi_status', (r) => pick(['MSS', 'MSS', 'MSI-H'], r, 3)),
    exported('sex', 'gender', () => 'F', { F: 'female' }),
    exported('BMI', 'bmi', (r) => (22 + ((r * 37) % 180) / 10).toFixed(1)),
    exported('vital_status', 'vital_status', (r) => pick(['Living', 'Living', 'Living', 'Deceased'], r, 4), {
        Living: 'Alive',
        Deceased: 'Dead',
    }),
    exported('race', 'race', (r) => pick(['White', 'White', 'Black or African American', 'Asian', 'Not Reported'], r, 5)),
    exported('Tumor_Stage_Pathological', 'uicc_pathologic_t', (r) => pick(['pT1a', 'pT1b', 'pT2', 'pT3a'], r, 6)),
    exported('tobacco_smoking_status', 'tobacco_smoking_status', (r) => pick(['Never', 'Never', 'Former', 'Current'], r, 7), {
        Never: 'Lifelong Non-Smoker',
        Former: 'Current Reformed Smoker',
        Current: 'Current Smoker',
    }),
    exported('age', 'age_at_diagnosis', (r) => String(45 + ((r * 11) % 38)), undefined, 'pending'),
    exported('diagnosis', 'primary_diagnosis', (r) => pick(['Endometrial carcinoma', 'Serous carcinoma'], r, 8), undefined, 'pending'),
    exported('residual_tumor', 'residual_disease', (r) => pick(['R0', 'R0', 'R1', 'RX'], r, 9), undefined, 'pending'),
    notExported('TMT_channel', 'pending'),
    notExported('peptide_ratio_norm', 'pending'),
    ...['Aliquot_ID', 'Plex', 'Proteomics_Batch', 'Specimen_Volume', 'Shipping_Temperature', 'Freezer_Box', 'QC_flag', 'Run_Date', 'Notes_internal'].map(
        (source) => notExported(source, 'unmapped'),
    ),
];

function demoExportPreview(params: URLSearchParams): ExportPreview {
    const offset = Math.max(0, Number(params.get('offset') ?? 0) || 0);
    const limit = Math.max(1, Number(params.get('limit') ?? 50) || 50);
    const changedOnly = params.get('changed_only') !== 'false';
    const focus = params.get('column');
    const outputs = demoExportColumns.filter((c) => c.target !== null);
    const rowCount = demoStudy.row_count ?? 0;

    const cells = Array.from({ length: rowCount }, (_, r) =>
        outputs.map((c) => {
            const before = c.value(r);
            return { before, after: c.rewrite?.[before] ?? before };
        }),
    );
    const changed = (r: number, j: number) => cells[r][j].before !== cells[r][j].after;

    const columns: ExportColumnChange[] = demoExportColumns.map((c) => {
        const j = outputs.indexOf(c);
        const counts = new Map<string, { before: string; after: string; count: number }>();
        if (j !== -1) {
            cells.forEach((row) => {
                const { before, after } = row[j];
                if (before === after) return;
                const key = `${before}\u0000${after}`;
                counts.set(key, { before, after, count: (counts.get(key)?.count ?? 0) + 1 });
            });
        }
        const value_changes = [...counts.values()]
            .sort((a, b) => b.count - a.count || a.before.localeCompare(b.before))
            .map((v) => ({ ...v, reason: 'ontology' as const }));
        return {
            source: c.source,
            target: c.target,
            action: c.action,
            mapping_status: c.mapping_status,
            drop_reason: c.target === null ? 'no_target' : null,
            conflicts_with: null,
            changed_cells: value_changes.reduce((sum, v) => sum + v.count, 0),
            value_changes,
            more_value_changes: 0,
        };
    });

    const focusIndex = focus ? outputs.findIndex((c) => c.target === focus) : -1;
    const lines = cells
        .map((_, r) => r)
        .filter((r) => !changedOnly || (focusIndex !== -1 ? changed(r, focusIndex) : outputs.some((_, j) => changed(r, j))));
    const changedCells = columns.reduce((sum, c) => sum + c.changed_cells, 0);
    const count = (action: ExportColumnChange['action']) => demoExportColumns.filter((c) => c.action === action).length;

    return {
        study_id: DEMO_STUDY_ID,
        summary: {
            rows: rowCount,
            columns_before: demoExportColumns.length,
            columns_after: outputs.length,
            renamed: count('renamed'),
            matched: count('matched'),
            kept: count('kept'),
            dropped: count('dropped'),
            pending: outputs.filter((c) => c.mapping_status === 'pending').length,
            changed_cells: changedCells,
            changed_rows: cells.filter((_, r) => outputs.some((__, j) => changed(r, j))).length,
            compared_cells: rowCount * outputs.length,
        },
        columns,
        rows: {
            total: lines.length,
            offset,
            limit,
            columns: outputs.map((c) => c.target as string),
            items: lines.slice(offset, offset + limit).map((r) => ({
                line: r + 1,
                values: cells[r].map((cell) => cell.after),
                changes: cells[r].flatMap((cell, j) =>
                    cell.before !== cell.after ? [{ column: j, before: cell.before, reason: 'ontology' as const }] : [],
                ),
            })),
        },
    };
}

/** Return a canned response for a GET while in guest preview, or null if the
 *  path has no fixture (caller then blocks the call). Writes always get null. */
export function guestFixture(path: string, method: string): { data: unknown } | null {
    if (method.toUpperCase() !== 'GET') return null;
    const p = path.split('?')[0];
    switch (p) {
        case '/studies':
            return { data: [demoStudy] };
        case `/studies/${DEMO_STUDY_ID}`:
            return { data: demoStudy };
        case `/mappings/${DEMO_STUDY_ID}`:
            return { data: demoMappings };
        case `/mappings/${DEMO_STUDY_ID}/review-queue`:
            return { data: demoReviewQueue };
        case `/ontology/mappings/${DEMO_STUDY_ID}`:
            return { data: demoOntology };
        case `/quality/${DEMO_STUDY_ID}`:
            return { data: demoQuality };
        case `/export/${DEMO_STUDY_ID}/preview`:
            return { data: demoExportPreview(new URLSearchParams(path.split('?')[1] ?? '')) };
        case '/schema-versions':
        case '/target-schemas':
            return { data: [] };
        default:
            return null;
    }
}
