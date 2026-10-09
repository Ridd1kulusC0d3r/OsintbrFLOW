import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { resolve } from 'path'

// Portable laboratory: no native editor, router generation or database services.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist-brasil',
    rollupOptions: { input: resolve(__dirname, 'brasil.html') }
  }
})
