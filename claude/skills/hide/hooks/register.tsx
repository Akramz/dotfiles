import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { HiddenPane } from '../types'

const open = atom({ plugin: 'hide', key: 'open' } as const, [] as HiddenPane[])
const hidden = atom({ plugin: 'hide', key: 'hidden' } as const, [] as HiddenPane[])

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'hide', description: 'Hide the side panes, or bring them back' })
    return next(e)
  })

  on('ui.open', async ($, e, next) => {
    const result = await next(e)
    const pane = { id: e.id, title: e.title ?? e.id }
    await update($, open, panes => [...panes.filter(p => p.id !== e.id), pane])
    return result
  })

  on('ui.close', async ($, e, next) => {
    const result = await next(e)
    await update($, open, panes => panes.filter(p => p.id !== e.id))
    return result
  })

  on('command.run', { command: 'hide' }, async $ => {
    const toShow = await read($, hidden)
    if (toShow.length) {
      await update($, hidden, () => [])
      for (const pane of toShow) await $.ui.open(pane)
      return { text: 'Side panes shown.' }
    }
    const toHide = await read($, open)
    await update($, hidden, () => toHide)
    for (const pane of toHide) await $.ui.close({ id: pane.id })
    return { text: toHide.length ? 'Side panes hidden. /hide brings them back.' : 'No side panes open.' }
  })
}
