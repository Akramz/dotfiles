export type Commit = { date: string; subject: string }

export type Repo = { name: string; commits: Commit[] }

export type Contributions =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; error: string }
  | { status: 'ready'; repos: Repo[]; scanned: number }

declare module 'claude-code' {
  interface PluginState {
    'weekly-git-commits': { contributions: Contributions }
  }
}
