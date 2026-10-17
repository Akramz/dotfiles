export type HiddenPane = { id: string; title: string }

declare module 'claude-code' {
  interface PluginState {
    'hide': { open: HiddenPane[]; hidden: HiddenPane[] }
  }
}
