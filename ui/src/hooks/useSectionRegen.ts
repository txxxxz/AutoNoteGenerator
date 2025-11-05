import { useState } from 'react';

export const useSectionRegen = () => {
  const [pendingSection, setPendingSection] = useState<string | null>(null);
  const startRegen = (sectionId: string) => setPendingSection(sectionId);
  const finishRegen = () => setPendingSection(null);
  return { pendingSection, startRegen, finishRegen };
};
