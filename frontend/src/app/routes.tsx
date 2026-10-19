import { Navigate, type RouteObject } from 'react-router'

import { NotFound } from '@/features/placeholder/NotFound'
import { SectionPlaceholder } from '@/features/placeholder/SectionPlaceholder'

import { AppShell } from './AppShell'
import {
  ArtIndex,
  ArtPage,
  EnemiesIndex,
  EnemiesPage,
  ExportIndex,
  ExportPage,
  ItemsIndex,
  ItemsPage,
  LibraryPage,
  LoreIndex,
  LorePage,
  MechanicsIndex,
  MechanicsPage,
  PlaytestIndex,
  PlaytestPage,
  SettingsPage,
  StoryIndex,
  StoryPage,
  WritingIndex,
  WritingPage,
} from './lazyPages'
import { Page } from './Page'
import { SECTIONS } from './sections'

const BUILT = new Set([
  'art',
  'export',
  'library',
  'story',
  'mechanics',
  'enemies',
  'items',
  'playtest',
  'lore',
  'writing',
  'settings',
])

export const routes: RouteObject[] = [
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/story" replace /> },
      {
        path: 'library',
        element: (
          <Page>
            <LibraryPage />
          </Page>
        ),
      },
      {
        path: 'story',
        element: (
          <Page>
            <StoryIndex />
          </Page>
        ),
      },
      {
        path: 'story/:bookId',
        element: (
          <Page>
            <StoryPage />
          </Page>
        ),
      },
      {
        path: 'mechanics',
        element: (
          <Page>
            <MechanicsIndex />
          </Page>
        ),
      },
      {
        path: 'mechanics/:seriesId',
        element: (
          <Page>
            <MechanicsPage />
          </Page>
        ),
      },
      {
        path: 'enemies',
        element: (
          <Page>
            <EnemiesIndex />
          </Page>
        ),
      },
      {
        path: 'enemies/:seriesId',
        element: (
          <Page>
            <EnemiesPage />
          </Page>
        ),
      },
      {
        path: 'items',
        element: (
          <Page>
            <ItemsIndex />
          </Page>
        ),
      },
      {
        path: 'items/:seriesId',
        element: (
          <Page>
            <ItemsPage />
          </Page>
        ),
      },
      {
        path: 'playtest',
        element: (
          <Page>
            <PlaytestIndex />
          </Page>
        ),
      },
      {
        path: 'playtest/:bookId',
        element: (
          <Page>
            <PlaytestPage />
          </Page>
        ),
      },
      {
        path: 'lore',
        element: (
          <Page>
            <LoreIndex />
          </Page>
        ),
      },
      {
        path: 'lore/:seriesId',
        element: (
          <Page>
            <LorePage />
          </Page>
        ),
      },
      {
        path: 'art',
        element: (
          <Page>
            <ArtIndex />
          </Page>
        ),
      },
      {
        path: 'art/:seriesId',
        element: (
          <Page>
            <ArtPage />
          </Page>
        ),
      },
      {
        path: 'export',
        element: (
          <Page>
            <ExportIndex />
          </Page>
        ),
      },
      {
        path: 'export/:bookId',
        element: (
          <Page>
            <ExportPage />
          </Page>
        ),
      },
      {
        path: 'writing',
        element: (
          <Page>
            <WritingIndex />
          </Page>
        ),
      },
      {
        path: 'writing/:bookId',
        element: (
          <Page>
            <WritingPage />
          </Page>
        ),
      },
      {
        path: 'settings',
        element: (
          <Page>
            <SettingsPage />
          </Page>
        ),
      },
      ...SECTIONS.filter((s) => !BUILT.has(s.id)).map((s) => ({
        path: s.path.slice(1),
        element: <SectionPlaceholder section={s} />,
      })),
      { path: '*', element: <NotFound /> },
    ],
  },
]
