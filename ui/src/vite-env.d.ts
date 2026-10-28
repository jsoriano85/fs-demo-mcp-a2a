/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_COORDINATOR_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
