import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Commit, Contributions, Repo } from '../types'

const PANE = 'weekly-git-commits'
const contributions = atom({ plugin: 'weekly-git-commits', key: 'contributions' } as const, { status: 'idle' })
let isLoading = false

// WEEKLY_GIT_ROOT: where to look for repos (default ~/projects).
// WEEKLY_GIT_AUTHOR: git --author pattern (default your global git user.email).
async function scan($: EngineInterface) {
  const root = (await $.env.get('WEEKLY_GIT_ROOT')) || `${await $.env.get('HOME')}/projects`
  const author = (await $.env.get('WEEKLY_GIT_AUTHOR'))
    || (await $.process.run(['git', 'config', '--global', '--includes', 'user.email'])).stdout.trim()
  if (!author) throw new Error('Set git user.email or WEEKLY_GIT_AUTHOR')
  const found = await $.process.run(
    ['find', root, '-maxdepth', '5', '(', '-name', 'node_modules', '-o', '-name', '.venv', ')', '-prune', '-o', '-name', '.git', '-print', '-prune'],
    { timeoutMs: 60_000 },
  )
  const dirs = found.stdout.split('\n').filter(Boolean).map(p => p.slice(0, -'/.git'.length))

  const repos: Repo[] = []
  for (let i = 0; i < dirs.length; i += 16) {
    const batch = await Promise.all(
      dirs.slice(i, i + 16).map(async (dir): Promise<Repo> => {
        const log = await $.process.run([
          'git', '-C', dir, 'log', '--all', '--since=7 days ago', '--regexp-ignore-case', `--author=${author}`,
          '--date=format-local:%a %m-%d %H:%M', '--format=%ad%x09%s',
        ])
        const commits: Commit[] = log.stdout.split('\n').filter(Boolean).map(line => {
          const [date = '', ...subject] = line.split('\t')
          return { date, subject: subject.join('\t') }
        })
        return { name: dir.slice(root.length + 1), commits }
      }),
    )
    repos.push(...batch.filter(repo => repo.commits.length))
  }
  repos.sort((a, b) => b.commits.length - a.commits.length || a.name.localeCompare(b.name))

  return { repos, scanned: dirs.length }
}

async function refresh($: EngineInterface) {
  if (isLoading) return
  isLoading = true
  await update($, contributions, (): Contributions => ({ status: 'loading' }))
  try {
    const result = await scan($)
    await update($, contributions, (): Contributions => ({ status: 'ready', ...result }))
  } catch (err) {
    await update($, contributions, (): Contributions => ({ status: 'error', error: String(err) }))
  } finally {
    isLoading = false
  }
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'weekly-git-commits',
      description: 'Rank repos under ~/projects (or $WEEKLY_GIT_ROOT) by your commits in the last 7 days',
    })
    return next(e)
  })

  on('command.run', { command: 'weekly-git-commits' }, async $ => {
    await $.ui.open({ id: PANE, title: 'Weekly git commits' })
    $.clock.after(0, () => void refresh($))
    return { text: 'Opened the weekly git commits pane.' }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button } = $.ui.resolve(e)
    const state = await read($, contributions)
    const reload = <Button key="refresh" label="Refresh" hotkey="r" onPress={() => refresh($)} />

    if (state.status === 'error') {
      return (
        <Box flexDirection="column">
          <Text color="red">{state.error}</Text>
          {reload}
        </Box>
      )
    }
    if (state.status !== 'ready') return <Text dimColor>Scanning repos…</Text>

    const { repos } = state
    const total = repos.reduce((n, r) => n + r.commits.length, 0)
    const width = String(repos[0]?.commits.length ?? 0).length

    return (
      <Box flexDirection="column">
        <Box>
          <Text dimColor>
            {total} commits in {repos.length} of {state.scanned} repos, last 7 days{' '}
          </Text>
          {reload}
        </Box>
        {repos.map(repo => (
          <Box flexDirection="column" marginTop={1}>
            <Box>
              <Text bold color="cyan">{String(repo.commits.length).padStart(width)} </Text>
              <Text bold>{repo.name}</Text>
            </Box>
            {repo.commits.map(c => (
              <Box>
                <Box flexShrink={0}>
                  <Text dimColor>{' '.repeat(width + 1)}{c.date}  </Text>
                </Box>
                <Text wrap="truncate">{c.subject}</Text>
              </Box>
            ))}
          </Box>
        ))}
      </Box>
    )
  })
}
