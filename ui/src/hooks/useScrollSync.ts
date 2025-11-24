import { useEffect, useState } from 'react';

export const useScrollSync = (sectionIds: string[]) => {
  const [activeId, setActiveId] = useState<string | null>(null);

  useEffect(() => {
    if (!sectionIds.length) {
      return;
    }
    const observers: IntersectionObserver[] = [];
    const pending = new Set(sectionIds);

    const register = (id: string, element: Element) => {
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
      pending.delete(id);
    };

    const tryRegister = (id: string) => {
      const element = document.querySelector(`[data-section-id="${id}"]`);
      if (element) {
        register(id, element);
      }
    };

    pending.forEach((id) => {
      tryRegister(id);
    });

    const interval = window.setInterval(() => {
      if (!pending.size) {
        window.clearInterval(interval);
        return;
      }
      pending.forEach((id) => tryRegister(id));
    }, 500);

    return () => {
      window.clearInterval(interval);
      observers.forEach((observer) => observer.disconnect());
    };
  }, [sectionIds.join(',')]);

  return { activeId, setActiveId };
};
