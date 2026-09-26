/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_AUTH_MODE?: string;
  readonly VITE_COGNITO_ISSUER?: string;
  readonly VITE_COGNITO_CLIENT_ID?: string;
  readonly VITE_COGNITO_AUTH_DOMAIN?: string;
  readonly VITE_PRIVATE_TEST_PITCH_ID?: string;
  readonly VITE_PRIVATE_TEST_VIDEO_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
