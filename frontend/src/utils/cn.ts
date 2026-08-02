import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * Merge Tailwind class names, resolving conflicts in favour of the last value.
 *
 * Lives in `utils/` rather than shadcn's default `lib/utils.ts` because the
 * SSOT fixes the `src` folder set and there is no `lib/`. The `components.json`
 * alias points here so generated components resolve correctly.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}
