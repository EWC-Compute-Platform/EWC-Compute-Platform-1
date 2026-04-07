# Minimum viable frontend file set for CI to pass:

```
frontend/
├── package.json          ← must have correct scripts AND devDependencies
├── tsconfig.json         ← must have correct paths/jsx setting
├── tsconfig.node.json    ← needed by Vite
├── vite.config.ts        ← must exist and be valid TS
├── eslint.config.js      ← or .eslintrc.json / .eslintrc.cjs
├── index.html            ← Vite entry point 
└── src/
    ├── main.tsx          ← root React entry
    ├── App.tsx           ← root component
    └── vite-env.d.ts     ← Vite type declarations
```
