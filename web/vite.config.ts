import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: './', // relative base so the static fallback build works from any path
  server: { port: 5173, host: '127.0.0.1' },
  build: {
    target: 'es2022',
    // Each environment is lazy-loaded (design spec, Performance). Keeping three.js in
    // its own chunk means the 2D path never downloads the 3D runtime.
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('three') || id.includes('@react-three')) return 'three';
        },
      },
    },
  },
});
