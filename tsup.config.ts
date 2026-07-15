import { defineConfig } from 'tsup';

export default defineConfig({
  entry: {
    cli: 'src/truesignal/cli.ts',
    index: 'src/truesignal/index.ts',
  },
  format: ['esm'],
  target: 'node18',
  dts: true,
  clean: true,
  splitting: false,
  sourcemap: true,
});
