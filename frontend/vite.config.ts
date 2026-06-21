import os from 'node:os'
import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'

// Print an extra "Network (host)" line using the machine hostname (or an
// explicit VITE_PUBLIC_HOST, e.g. injected by docker-compose) instead of only
// localhost and the unreachable container IP that Vite shows by default.
function printHostUrl(): Plugin {
  return {
    name: 'print-host-url',
    configureServer(server) {
      const displayHost = process.env.VITE_PUBLIC_HOST || os.hostname()
      const printUrls = server.printUrls.bind(server)
      server.printUrls = () => {
        printUrls()
        const address = server.httpServer?.address()
        const port =
          typeof address === 'object' && address ? address.port : server.config.server.port
        server.config.logger.info(
          `  \x1b[32m➜\x1b[0m  \x1b[1mNetwork (host):\x1b[0m http://${displayHost}:${port}/`
        )
      }
    },
  }
}

// `server.*` and the host-URL plugin only apply to the `vite` dev server
// (command === 'serve'). The production build (`vite build` -> nginx, see
// frontend/Dockerfile) never reads them, so binding to all interfaces and
// disabling the host check stay confined to the docker dev stack.
export default defineConfig(({ command }) => ({
  plugins: [react(), ...(command === 'serve' ? [printHostUrl()] : [])],
  ...(command === 'serve' && {
    server: {
      host: true,
      port: 5173,
      proxy: {
        '/api': {
          target: process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000',
          changeOrigin: true,
        },
      },
      allowedHosts: true,
    },
  }),
}))
