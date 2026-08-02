/** Application-wide state. Deliberately split by concern to bound re-renders. */

export { AppProviders } from './AppProviders'
export { BootContext, BootProvider } from './BootContext'
export { LiveContext, LiveProvider } from './LiveContext'
export { SidebarContext, SidebarProvider } from './SidebarContext'
export { ThemeContext, ThemeProvider } from './ThemeContext'
export type { ResolvedTheme, ThemePreference } from './ThemeContext'
