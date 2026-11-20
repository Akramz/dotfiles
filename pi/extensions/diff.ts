// Claude Code's /diff, small: the working tree's `git diff --stat` against HEAD, plus untracked files,
// in a box. /hunk opens the full live diff.
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Text } from "@earendil-works/pi-tui";
import { showBox } from "./lib/box.ts";

export default function (pi: ExtensionAPI) {
	pi.registerCommand("diff", {
		description: "Show the working-tree diff stat (git diff --stat HEAD) and untracked files",
		handler: async (_args, ctx) => {
			const git = (...a: string[]) => pi.exec("git", ["-C", ctx.cwd, ...a]);
			const stat = await git("diff", "--stat", "--color=always", "HEAD");
			if (stat.code !== 0) return ctx.ui.notify("Not a git repository", "warning");
			const untracked = (await git("ls-files", "--others", "--exclude-standard")).stdout.trim();
			const body = [
				stat.stdout.trimEnd() || "No changes to tracked files.",
				untracked && `\nUntracked:\n${untracked.split("\n").map((f) => `  ${f}`).join("\n")}`,
			]
				.filter(Boolean)
				.join("\n");

			if (ctx.mode !== "tui") return ctx.ui.notify(body, "info");
			await showBox(ctx, "diff · working tree vs HEAD", new Text(body, 1, 1), "/hunk for the full diff");
		},
	});
}
