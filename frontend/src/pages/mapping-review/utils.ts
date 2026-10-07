export const STAGE_ORDER = ['stage1', 'stage2', 'stage3', 'stage4', 'invalid', 'unmapped'] as const;

export const STAGE_META: Record<string, { label: string; bar: string }> = {
  stage1: { label: 'S1 Dict/Fuzzy', bar: 'bg-blue-500' },
  stage2: { label: 'S2 Value/Ontology', bar: 'bg-orange-500' },
  stage3: { label: 'S3 Semantic', bar: 'bg-teal-500' },
  stage4: { label: 'S4 LLM', bar: 'bg-pink-500' },
  invalid: { label: 'Invalid', bar: 'bg-red-500' },
  unmapped: { label: 'Unmapped', bar: 'bg-gray-400' },
};
