import './player.css'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { Root } from './Root'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
)

// Offline play once installed (only over http(s); file:// can't register workers).
if ('serviceWorker' in navigator && location.protocol.startsWith('http') && window.GAMEBOOK) {
  navigator.serviceWorker.register('./sw.js').catch(() => {})
}
