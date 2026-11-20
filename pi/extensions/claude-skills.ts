// Skills, commands and MCP servers the Claude Code way: `/push` instead of `/skill:push`, the skills and
// MCP servers of the plugins enabled in ~/.claude/settings.json, and Claude's own MCP servers.
import { existsSync, readdirSync, readFileSync, realpathSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { type ExtensionAPI, loadSkillsFromDir } from "@earendil-works/pi-coding-agent";

const home = homedir();
const json = (p: string) => {
	try {
		return JSON.parse(readFileSync(p, "utf8"));
	} catch {
		return {};
	}
};
const subdirs = (p: string) => (existsSync(p) ? readdirSync(p).map((n) => join(p, n)) : []);

function pluginRoots(): string[] {
	const enabled = json(`${home}/.claude/settings.json`).enabledPlugins ?? {};
	const installed = json(`${home}/.claude/plugins/installed_plugins.json`).plugins ?? {};
	return [
		...Object.entries(installed)
			.filter(([id]) => enabled[id])
			.map(([, v]: [string, any]) => v?.[0]?.installPath)
			.filter((p): p is string => !!p && existsSync(p)),
		// Plugins that live inside the skills folder (paper-search, ty-lsp).
		...subdirs(`${home}/.claude/skills`).filter((d) => existsSync(`${d}/.claude-plugin`)),
	];
}

// claude.ai keeps one synced bucket per account; settings.json hides them all, and this adds back the newest.
function newestSyncedBucket(): string[] {
	const buckets = subdirs(`${home}/.claude/skills/synced`).filter((d) => existsSync(`${d}/manifest.json`));
	const updated = (d: string) => json(`${d}/manifest.json`).lastUpdated ?? 0;
	return buckets.sort((a, b) => updated(b) - updated(a)).slice(0, 1);
}

export default function (pi: ExtensionAPI) {
	const roots = pluginRoots();
	const skillDirs = [...roots.map((r) => `${r}/skills`).filter(existsSync), ...newestSyncedBucket()];

	pi.on("resources_discover", async (event) => {
		// In ~ this is the user skills folder, which pi already loads as ~/.pi/agent/skills.
		const project = join(event.cwd, ".claude", "skills");
		const isProject = existsSync(project) && realpathSync(project) !== realpathSync(`${home}/.claude/skills`);
		// Claude Code slash commands (.claude/commands/*.md) are plain prompts, which pi calls prompt templates.
		const commands = [`${home}/.claude/commands`, join(event.cwd, ".claude", "commands")].filter(existsSync);
		return {
			skillPaths: [...skillDirs, ...(isProject ? [project] : [])],
			promptPaths: [...new Set(commands.map((p) => realpathSync(p)))],
		};
	});

	const servers = {
		...json(`${home}/.claude.json`).mcpServers,
		...Object.assign({}, ...roots.flatMap((r) => [
			json(`${r}/.claude-plugin/plugin.json`).mcpServers,
			json(`${r}/.mcp.json`).mcpServers,
		])),
	};
	for (const [name, cfg] of Object.entries(servers)) {
		try {
			pi.registerMcpServer(name, cfg as any);
		} catch {}
	}

	// Register `/name` now, so it autocompletes. claude-hooks.ts owns /bye.
	const seen = new Set(["bye"]);
	for (const dir of [`${home}/.pi/agent/skills`, `${home}/.agents/skills`, ...skillDirs]) {
		for (const s of loadSkillsFromDir({ dir, source: "claude" }).skills) {
			if (seen.has(s.name)) continue;
			seen.add(s.name);
			pi.registerCommand(s.name, {
				description: s.description.slice(0, 120),
				handler: async (args) =>
					pi.sendUserMessage(`/skill:${s.name} ${args}`.trim(), { expandPromptTemplates: true, deliverAs: "followUp" }),
			});
		}
	}

	// Project skills (.claude/skills) are found later, so map `/name` to `/skill:name` here.
	pi.on("input", async (event) => {
		const m = event.text.match(/^\/([a-z0-9][a-z0-9-]*)(\s[\s\S]*)?$/);
		if (m && pi.getCommands().some((c) => c.name === `skill:${m[1]}`)) {
			return { action: "transform", text: `/skill:${m[1]}${m[2] ?? ""}` };
		}
		return { action: "continue" };
	});
}
