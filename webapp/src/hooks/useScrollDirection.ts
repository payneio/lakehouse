import { useEffect, useRef, useState } from 'react';

/**
 * Detects scroll direction (up/down) with debouncing
 * Only active on mobile viewports (< 1024px)
 *
 * @param threshold - Minimum pixels scrolled before direction change (default: 10)
 * @param scrollElement - Optional scrollable element (defaults to window)
 * @returns 'up' | 'down' - Current scroll direction
 */
export function useScrollDirection(
  threshold = 10,
  scrollElement?: HTMLElement | null
): 'up' | 'down' {
  const [scrollDir, setScrollDir] = useState<'up' | 'down'>('up');
  const lastScrollY = useRef(0);

  useEffect(() => {
    // Only run on mobile (< 1024px, Tailwind's lg breakpoint)
    const isMobile = () => window.innerWidth < 1024;

    const handleScroll = () => {
      if (!isMobile()) {
        return;
      }

      // Get scroll position from element or window
      const currentScrollY = scrollElement ? scrollElement.scrollTop : window.scrollY;
      const diff = currentScrollY - lastScrollY.current;

      // Only update if scrolled past threshold (prevents jitter)
      if (Math.abs(diff) > threshold) {
        const newDir = diff > 0 ? 'down' : 'up';
        setScrollDir(newDir);
        lastScrollY.current = currentScrollY;
      }
    };

    // Attach listener to element or window
    const target = scrollElement || window;
    target.addEventListener('scroll', handleScroll, { passive: true });

    return () => {
      target.removeEventListener('scroll', handleScroll);
    };
  }, [threshold, scrollElement, scrollDir]);

  return scrollDir;
}
