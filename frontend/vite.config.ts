import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { cpSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

// SDK 3.0.2 deliberately leaves its lazy WASM import out of Vite's graph.
// Serve the exact installed SDK runtime at a stable URL in dev and production.
const runtimeSource = fileURLToPath(new URL('./node_modules/@reactor-team/js-sdk/dist/wasm/', import.meta.url));
const runtimePublic = fileURLToPath(new URL('./public/reactor/wasm/', import.meta.url));
mkdirSync(runtimePublic, { recursive: true });
cpSync(runtimeSource, runtimePublic, { recursive: true });

export default defineConfig({
 plugins:[{
  name:'reactor-wasm-runtime',
  enforce:'pre',
  transform(code,id){
   if(id.includes('@reactor-team/js-sdk/dist/index.js')){
    return code.replace('"./wasm/reactor_wasm.js"','window.location.origin + "/reactor/wasm/reactor_wasm.js"');
   }
  },
 },react()],
 optimizeDeps:{exclude:['@reactor-team/js-sdk'],include:['awaitqueue','mp4box','hls.js']},
 server:{host:'127.0.0.1',port:5190,strictPort:true,proxy:{'/api':'http://127.0.0.1:8190','/uploads':'http://127.0.0.1:8190'}},
 preview:{host:'127.0.0.1',port:5190,strictPort:true},
});
