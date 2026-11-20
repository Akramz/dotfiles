// Gives pi the context Claude Code loads: the @ imports in CLAUDE.md files (pi reads the
// files but not their imports) and the project's auto-memory index, once per session.
import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const home = homedir();
const read = (p: string) => (existsSync(p) ? readFileSync(p, "utf8").trim() : "");
const expand = (p: string) => p.replace(/^~(?=\/)/, home);

function memoryDir(cwd: string): string {
	for (const f of ["settings.local.json", "settings.json"]) {
		try {
			const dir = JSON.parse(read(`${cwd}/.claude/${f}`) || "{}").autoMemoryDirectory;
			if (dir) return expand(dir);
		} catch {}
	}
	return `${home}/.claude/projects/${cwd.replace(/[^A-Za-z0-9]/g, "-")}/memory`;
}

export default function (pi: ExtensionAPI) {
	let sections: Record<string, string> | undefined;

	pi.on("before_agent_start", async (event, ctx) => {
		const o = event.systemPromptOptions;
		sections ??= (() => {
			const paths = new Set(o.contextFiles.flatMap((f) => [...f.content.matchAll(/^@(\S+)\s*$/gm)].map((m) => expand(m[1]))));
			const imports = [...paths].map((p) => [p, read(p)]).filter(([, t]) => t).map(([p, t]) => `<file path="${p}">\n${t}\n</file>`);
			const dir = memoryDir(ctx.cwd);
			const index = read(`${dir}/MEMORY.md`);
			return {
				...(imports.length ? { claude_imports: imports.join("\n\n") } : {}),
				memory: [
					read(`${home}/.pi/agent/memory.md`),
					`This project's memory folder: ${dir}`,
					index ? `Its MEMORY.md, as of session start:\n\n${index}` : "It has no MEMORY.md yet.",
				].filter(Boolean).join("\n\n"),
			};
		})();
		Object.assign(o.sections, sections);
	});
}
