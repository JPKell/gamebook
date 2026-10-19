/** The standalone web player: one classic script so it also runs from file://. */
import { fileURLToPath, URL } from 'node:url'

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  base: './',
  publicDir: false, // the app's public files (favicon) aren't the player's
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  build: {
    outDir: 'dist-player',
    emptyOutDir: true,
    modulePreload: false,
    cssCodeSplit: false,
    rollupOptions: {
      input: fileURLToPath(new URL('./player.html', import.meta.url)),
      output: {
        format: 'iife',
        inlineDynamicImports: true,
        entryFileNames: 'assets/player.js',
        assetFileNames: 'assets/[name][extname]',
      },
    },
  },
})
