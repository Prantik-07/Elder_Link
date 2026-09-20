import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // The deployed API and S3 bucket allow CORS only from http://localhost:5173.
  // strictPort makes Vite fail loudly instead of silently starting on
  // 5174/5175/..., where every API call and audio upload would be blocked.
  server: { port: 5173, strictPort: true },
})
