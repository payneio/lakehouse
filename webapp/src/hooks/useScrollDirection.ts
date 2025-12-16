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
    console.log('[useScrollDirection] Hook initialized', {
      threshold,
      hasScrollElement: !!scrollElement
    });

    // Only run on mobile (< 1024px, Tailwind's lg breakpoint)
    const isMobile = () => window.innerWidth < 1024;

    const handleScroll = () => {
      const mobile = isMobile();
      console.log('[useScrollDirection] Scroll event fired', {
        isMobile: mobile,
        windowWidth: window.innerWidth
      });

      if (!mobile) {
        console.log('[useScrollDirection] Skipping - not mobile');
        return;
      }

      // Get scroll position from element or window
      const currentScrollY = scrollElement ? scrollElement.scrollTop : window.scrollY;

      console.log('[useScrollDirection] Scroll position', {
        hasElement: !!scrollElement,
        currentScrollY,
        lastScrollY: lastScrollY.current,
        diff: currentScrollY - lastScrollY.current
      });

      const diff = currentScrollY - lastScrollY.current;

      // Only update if scrolled past threshold (prevents jitter)
      if (Math.abs(diff) > threshold) {
        const newDir = diff > 0 ? 'down' : 'up';
        console.log('[useScrollDirection] Direction changed', {
          oldDir: scrollDir,
          newDir,
          diff
        });
        setScrollDir(newDir);
        lastScrollY.current = currentScrollY;
      } else {
        console.log('[useScrollDirection] Below threshold, not updating');
      }
    };

    // Attach listener to element or window
    const target = scrollElement || window;
    console.log('[useScrollDirection] Attaching listener to:', target);
    target.addEventListener('scroll', handleScroll, { passive: true });

    return () => {
      console.log('[useScrollDirection] Cleaning up listener');
      target.removeEventListener('scroll', handleScroll);
    };
  }, [threshold, scrollElement, scrollDir]);

  return scrollDir;
}
