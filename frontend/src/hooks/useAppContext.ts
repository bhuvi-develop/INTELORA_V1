/**
 * Context accessors.
 *
 * Each throws when used outside its provider. A hard failure at development
 * time is far cheaper than a component silently rendering with default values
 * that happen to look plausible.
 */

import { useContext } from 'react'

import { BootContext } from '@/context/BootContext'
import { LiveContext } from '@/context/LiveContext'
import { SidebarContext } from '@/context/SidebarContext'
import { ThemeContext } from '@/context/ThemeContext'

export function useTheme() {
  const context = useContext(ThemeContext)
  if (!context) throw new Error('useTheme must be used within a ThemeProvider.')
  return context
}

export function useSidebar() {
  const context = useContext(SidebarContext)
  if (!context) throw new Error('useSidebar must be used within a SidebarProvider.')
  return context
}

export function useBoot() {
  const context = useContext(BootContext)
  if (!context) throw new Error('useBoot must be used within a BootProvider.')
  return context
}

export function useLive() {
  const context = useContext(LiveContext)
  if (!context) throw new Error('useLive must be used within a LiveProvider.')
  return context
}
