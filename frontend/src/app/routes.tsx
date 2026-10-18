import { Navigate, type RouteObject } from 'react-router'

import { NotFound } from '@/features/placeholder/NotFound'
import { SectionPlaceholder } from '@/features/placeholder/SectionPlaceholder'

import { AppShell } from './AppShell'
import {
  EnemiesIndex,
  EnemiesPage,
  ItemsIndex,
  ItemsPage,
  LibraryPage,
  MechanicsIndex,
  MechanicsPage,
  PlaytestIndex,
  PlaytestPage,
  StoryIndex,
  StoryPage,
} from './lazyPages'
import { Page } from './Page'
import { SECTIONS } from './sections'

const BUILT = new Set(['library', 'story', 'mechanics', 'enemies', 'items', 'playtest'])

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
      ...SECTIONS.filter((s) => !BUILT.has(s.id)).map((s) => ({
        path: s.path.slice(1),
        element: <SectionPlaceholder section={s} />,
      })),
      { path: '*', element: <NotFound /> },
    ],
  },
]
