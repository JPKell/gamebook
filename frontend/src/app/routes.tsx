import { Navigate, type RouteObject } from 'react-router'

import { NotFound } from '@/features/placeholder/NotFound'
import { SectionPlaceholder } from '@/features/placeholder/SectionPlaceholder'

import { AppShell } from './AppShell'
import { SECTIONS } from './sections'

export const routes: RouteObject[] = [
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/story" replace /> },
      ...SECTIONS.map((s) => ({
        path: s.path.slice(1),
        element: <SectionPlaceholder section={s} />,
      })),
      { path: '*', element: <NotFound /> },
    ],
  },
]
