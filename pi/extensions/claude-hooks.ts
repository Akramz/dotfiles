// The Claude Code hooks and mods from claude/settings.json, as pi events.
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const home = homedir();
const pidDir = `${home}/.pi/agent/pids`;
const pidFile = `${pidDir}/${process.pid}`;
const STOP = new Set(["a", "an", "and", "the", "of", "for", "to", "in", "on", "with", "from", "by"]);

// Run a Claude Code hook script with a Claude-shaped event on stdin; returns its JSON reply.
function claudeHook(script: string, event: object): Promise<any> {
	return new Promise((resolve) => {
		const p = spawn(`${home}/.claude/hooks/${script}`, [], { stdio: ["pipe", "pipe", "ignore"] });
		let out = "";
		p.stdout.on("data", (d) => (out += d));
		p.on("close", () => {
			try {
				resolve(JSON.parse(out));
			} catch {
				resolve({});
			}
		});
		p.on("error", () => resolve({}));
		p.stdin.end(JSON.stringify(event));
	});
}

const slug = (s: string, stop = new Set<string>()) =>
	(s.toLowerCase().match(/[a-z0-9]+/g) ?? []).filter((w) => !stop.has(w)).slice(0, 4).join("-");

export default function (pi: ExtensionAPI) {
	let timer: ReturnType<typeof setInterval> | undefined;
	let titling = false;

	pi.on("session_start", async (_event, ctx) => {
		// tmux-resurrect's agents.sh reads this to reopen the same session after a reboot.
		const file = ctx.sessionManager.getSessionFile();
		if (file) {
			mkdirSync(pidDir, { recursive: true });
			writeFileSync(pidFile, file);
		}

		// The agent-bar line (claude/skills/agent-bar): one shared file, refreshed every 10 s.
		if (!ctx.hasUI) return;
		const line = `${home}/.cache/agent-bar/line`;
		const tick = async () => {
			const fresh = existsSync(line) && Date.now() - statSync(line).mtimeMs < 9_500;
			const text = fresh ? readFileSync(line, "utf8") : (await pi.exec(`${home}/bin/agent_bar.py`, [])).stdout;
			ctx.ui.setStatus("agent-bar", text.trim() || undefined);
		};
		timer = setInterval(() => void tick().catch(() => {}), 10_000);
		void tick().catch(() => {});
	});

	pi.on("session_shutdown", async (event) => {
		clearInterval(timer);
		if (event.reason !== "quit") return;
		rmSync(pidFile, { force: true });
		await pi.exec(`${home}/.claude/hooks/sync_memories.sh`, []).catch(() => {});
	});

	pi.on("input", async (event, ctx) => {
		// html_plan_verify.py adds the Goal Verification rule to /html-plan.
		const cmd = event.text.match(/^\/(?:skill:)?(html-plan)\b/)?.[1];
		if (cmd) {
			const rule = (await claudeHook("html_plan_verify.py", { hook_event_name: "UserPromptExpansion", command_name: cmd }))
				.hookSpecificOutput?.additionalContext;
			if (rule && !event.text.includes(rule)) return { action: "transform", text: `${event.text}\n\n${rule}` };
		}

		// Name the session after the first real prompt (claude/hooks/auto_title.py). /name wins.
		if (ctx.hasUI && !titling && event.source === "interactive" && !pi.getSessionName() && !event.text.startsWith("/")) {
			titling = true;
			void titleFor(event.text, ctx).then((t) => {
				try {
					if (t && !pi.getSessionName()) pi.setSessionName(t);
				} catch {} // the session ended or was replaced meanwhile
			});
		}
		return { action: "continue" };
	});

	// ...and blocks a pack.mjs run whose plan lacks that section.
	pi.on("tool_result", async (event, ctx) => {
		if (event.toolName !== "bash" || !String((event.input as any)?.command).includes("pack.mjs")) return;
		const reply = await claudeHook("html_plan_verify.py", {
			hook_event_name: "PostToolUse", tool_name: "Bash", tool_input: event.input, cwd: ctx.cwd,
		});
		if (reply.decision === "block") return { content: [...event.content, { type: "text", text: reply.reason }], isError: true };
	});
}

async function titleFor(prompt: string, ctx: any): Promise<string> {
	const model = ctx.modelRegistry.find("github-copilot", "claude-haiku-5.5");
	try {
		const res = await ctx.modelRegistry.complete(model, {
			messages: [{
				role: "user",
				content: [{ type: "text", text: `Name this coding chat in 2 to 4 lowercase words joined by hyphens, like "fix-login-redirect". Reply with the name only.\n\n${prompt.slice(0, 2000)}` }],
				timestamp: Date.now(),
			}],
		}, { cacheRetention: "none" });
		return slug(res.content.filter((c: any) => c.type === "text").map((c: any) => c.text).join("")) || slug(prompt, STOP);
	} catch {
		return slug(prompt, STOP);
	}
}
