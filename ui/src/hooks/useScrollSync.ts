import { useEffect, useState } from 'react';

export const useScrollSync = (sectionIds: string[]) => {
  const [activeId, setActiveId] = useState<string | null>(null);

  useEffect(() => {
    if (!sectionIds.length) {
      return;
    }
    const observers: IntersectionObserver[] = [];

    sectionIds.forEach((id) => {
      const element = document.querySelector(`[data-section-id="${id}"]`);
      if (!element) return;
      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              setActiveId(id);
            }
          });
        },
        { rootMargin: '0px 0px -70% 0px' }
      );
      observer.observe(element);
      observers.push(observer);
    });

    return () => {
      observers.forEach((observer) => observer.disconnect());
    };
  }, [sectionIds.join(',')]);

  return { activeId, setActiveId };
};
