import type { Register } from 'claude-code'

const TOPICS = {
  red: 'bugs, errors, crashes, failing tests, incidents',
  orange: 'infrastructure, cloud, VMs, deploys, CI, Docker',
  yellow: 'writing, docs, notes, email, journal, slides',
  green: 'data, ML, geospatial, research, experiments, analysis',
  blue: 'building or changing app code, features, refactors',
  purple: 'planning, design, architecture, AI agents, reviews',
  pink: 'personal life, health, running, reading, fun',
  cyan: 'config, dotfiles, shell, tooling, setup, git',
}
const LABELS = Object.entries(TOPICS).map(([color, topics]) => `${color}: ${topics}`)

export const register: Register = on => {
  const seen = new Set<string>()

  on('prompt.submit', async ($, e, next) => {
    if (e.command || e.isMeta) return next(e)
    const id = await $.session.id()
    if (!seen.has(id) && seen.add(id) && (await $.session.turns()) <= 1) {
      void $.model
        .classify(e.text.slice(0, 2000), LABELS, { model: 'haiku' })
        .then(label => { if (label) return $.command.run({ command: 'color', args: label.split(':')[0] }) })
        .catch(() => {})
    }
    return next(e)
  })
}
