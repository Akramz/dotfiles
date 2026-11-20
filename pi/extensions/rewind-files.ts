// Claude Code-style /rewind for files. Snapshots the git worktree before each prompt and after each
// run, and when /tree (or /rewind) moves back, offers to put the files back as they were there.
// Snapshots live in a shadow repo under ~/.pi/agent/rewind, so the project's own git state is never
// touched. Ignored files and untracked files over 50 MB are left alone; outside a git repo, and in
// subagent processes (no UI), this does nothing.
import { createHash } from "node:crypto";
import { appendFileSync, mkdirSync, statSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const BIG = 50 * 1024 * 1024;

export default function (pi: ExtensionAPI) {
	let base: string[] | undefined;
	let top = "";
	let exclude = "";
	let session = "";

	const git = async (...args: string[]) => {
		const r = await pi.exec("git", [...base!, ...args], { timeout: 30_000 });
		if (r.code !== 0) throw new Error(r.stderr.trim() || `git ${args[0]} failed`);
		return r.stdout.trim();
	};
	const ref = (leaf: string | null | undefined) => `refs/pi/${session}/${leaf ?? "root"}`;
	const snapshot = async () => {
		// Keep big new files (rasters, checkpoints) out: hashing them would stall every prompt.
		const others = (await git("ls-files", "--others", "--exclude-standard", "-z")).split("\0").filter(Boolean);
		const big = others.filter((f) => {
			try {
				return statSync(join(top, f)).size > BIG;
			} catch {
				return false;
			}
		});
		if (big.length) appendFileSync(exclude, big.map((f) => `/${f}\n`).join(""));
		await git("add", "-A", ".");
		return git("write-tree");
	};
	const save = async (leaf: string | null | undefined) => {
		if (base) await snapshot().then((tree) => git("update-ref", ref(leaf), tree)).catch(() => {});
	};

	pi.on("session_start", async (_event, ctx) => {
		base = undefined;
		if (!ctx.hasUI) return;
		session = ctx.sessionManager.getSessionId();
		const r = await pi.exec("git", ["-C", ctx.cwd, "rev-parse", "--show-toplevel"]);
		if (r.code !== 0) return;
		top = r.stdout.trim();
		const dir = `${homedir()}/.pi/agent/rewind/${createHash("sha1").update(top).digest("hex").slice(0, 16)}`;
		mkdirSync(dir, { recursive: true });
		if ((await pi.exec("git", ["--git-dir", dir, "init", "-q"])).code !== 0) return;
		exclude = `${dir}/info/exclude`;
		base = ["-C", top, "--git-dir", dir, "--work-tree", top];
	});

	// Runs before pi saves the user message, so the leaf is the entry /tree lands on when you pick it.
	pi.on("message_end", async (event, ctx) => {
		if (event.message.role === "user") await save(ctx.sessionManager.getLeafId());
	});
	// The end of a run needs its own snapshot: hidden entries (a session title) can follow it.
	pi.on("agent_end", async (_event, ctx) => save(ctx.sessionManager.getLeafId()));

	pi.on("session_tree", async (event, ctx) => {
		if (!base || !ctx.hasUI) return;
		try {
			const current = await snapshot();
			await git("update-ref", ref(event.oldLeafId), current);
			const target = await git("rev-parse", "--verify", "-q", ref(event.newLeafId)).catch(() => "");
			if (!target || current === target) return;

			const files = (await git("diff", "--name-only", current, target)).split("\n");
			const shown = files.slice(0, 5).join(", ") + (files.length > 5 ? ", …" : "");
			const yes = `Restore ${files.length} file(s): ${shown}`;
			const choice = await ctx.ui.select("Files changed since this point. Restore them too?", [yes, "Keep files as they are"]);
			if (choice !== yes) return;
			await git("restore", `--source=${target}`, "--staged", "--worktree", "--", ".");
			ctx.ui.notify(`Restored ${files.length} file(s). /tree back to undo.`, "info");
		} catch (e) {
			ctx.ui.notify(`rewind-files: ${(e as Error).message}`, "error");
		}
	});
}
