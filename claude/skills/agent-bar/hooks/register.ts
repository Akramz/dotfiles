import type { Register } from 'claude-code'

// One line under the prompt, e.g. `$142 this month · waiting: api-2 · done: docs`.
// ~/bin/agent_bar.py writes it; every session reads the same file and reruns the script
// only when the file is a tick old, so thirty open sessions cost one run per tick.
const TICK = 10_000

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const home = await $.env.get('HOME')
    const line = `${home}/.cache/agent-bar/line`
    let shown: string | undefined

    const tick = async () => {
      const now = await $.clock.now()
      const isFresh = await $.fs.stat(line).then(s => now - s.mtimeMs < TICK - 500, () => false)
      const text = isFresh ? await $.fs.read(line) : (await $.process.run([`${home}/bin/agent_bar.py`])).stdout
      if (text.trim() !== shown) {
        shown = text.trim()
        $.ui.status(shown || undefined)
      }
    }

    $.clock.every(TICK, () => void tick().catch(() => {}))
    void tick().catch(() => {})

    return next(e)
  })
}
