import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Forward any /api call in dev to the FastAPI backend on :8000.
      // The frontend always talks to same-origin /api, so there is no CORS in dev.
      '/api': 'http://localhost:8000',
    },
  },
})
