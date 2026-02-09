import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(() => {
  // Allow dev access via tunnels (e.g. https://<random>.trycloudflare.com)
  // Vite blocks unknown hosts by default.
  const extraAllowedHosts = String(process.env.EASYAGENDA_ALLOWED_HOSTS || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)

  const allowedHosts = [
    // Allow all subdomains for common tunnel providers
    '.trycloudflare.com',
    '.ngrok.io',
    '.ngrok-free.app',
    ...extraAllowedHosts
  ]

  return {
    plugins: [react()],
    // Override for realistic tests against the live API:
    // PowerShell: $env:EASYAGENDA_API_TARGET='https://api.easy-agenda.com'
    //            $env:PORT='3003'
    //            npm run dev
    // NOTE: Vite reads env vars from the running shell; no .env required.
    server: {
      host: true,
      port: Number(process.env.PORT) || 3002,
      strictPort: false,
      hmr: true,
      allowedHosts,
      proxy: {
        // Proxy API requests to backend
        '^/api': {
          target: process.env.EASYAGENDA_API_TARGET || 'http://127.0.0.1:8000',
          changeOrigin: true,
          secure: false,
          rewrite: (path) => path.replace(/^\/api/, '')
        },
        // also proxy plain backend API paths (avoid proxying frontend routes like /dashboard and /booking)
        '^/(auth|admin|appointments|config|occupancy|availability|notifications|sync|interesses|agent)': {
          target: process.env.EASYAGENDA_API_TARGET || 'http://127.0.0.1:8000',
          changeOrigin: true,
          secure: false
        }
      }
    },
    preview: {
      host: true,
      port: Number(process.env.PORT) || 3002,
      strictPort: false
    }
  }
})
