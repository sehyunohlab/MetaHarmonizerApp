import type { OntologyMapping } from '../../api/types';

export const hasTerm = (m: OntologyMapping) => !!(m.curator_term ?? m.ontology_term);
