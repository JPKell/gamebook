import { Navigate, type RouteObject } from 'react-router'

import { NotFound } from '@/features/placeholder/NotFound'
import { SectionPlaceholder } from '@/features/placeholder/SectionPlaceholder'

import { AppShell } from './AppShell'
import { LibraryPage, StoryIndex, StoryPage } from './lazyPages'
import { Page } from './Page'
import { SECTIONS } from './sections'

const BUILT = new Set(['library', 'story'])

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
      ...SECTIONS.filter((s) => !BUILT.has(s.id)).map((s) => ({
        path: s.path.slice(1),
        element: <SectionPlaceholder section={s} />,
      })),
      { path: '*', element: <NotFound /> },
    ],
  },
]
