// Claude Code's /btw: ask a side question about the session. The session's model answers once, with
// no tools, and the answer shows in a box that is not saved to the session.
import { uuidv7 } from "@earendil-works/pi-ai";
import { convertToLlm, type ExtensionAPI, getMarkdownTheme, serializeConversation } from "@earendil-works/pi-coding-agent";
import { Markdown } from "@earendil-works/pi-tui";
import { showBox } from "./lib/box.ts";

const MAX_CHARS = 200_000;

export default function (pi: ExtensionAPI) {
	pi.registerCommand("btw", {
		description: "Ask a side question without adding it to the chat",
		handler: async (question, ctx) => {
			question = question.trim();
			if (!question) return ctx.ui.notify("Usage: /btw <question>", "warning");
			if (!ctx.model) return ctx.ui.notify("No model selected", "warning");

			const messages = ctx.sessionManager.getBranch().flatMap((e: any) => (e.type === "message" ? [e.message] : []));
			const prompt = [
				"Below is a coding-agent session. The user has a quick side question about it.",
				"Answer briefly and directly from the session. You have no tools.",
				"",
				"<session>",
				serializeConversation(convertToLlm(messages)).slice(-MAX_CHARS),
				"</session>",
				"",
				`Side question: ${question}`,
			].join("\n");

			ctx.ui.setStatus("btw", "btw: thinking…");
			let answer: string;
			try {
				const r = await ctx.modelRegistry.complete(
					ctx.model,
					{ messages: [{ role: "user", content: [{ type: "text", text: prompt }], timestamp: Date.now() }] },
					{ cacheRetention: "none", sessionId: uuidv7() },
				);
				answer = r.content.flatMap((b: any) => (b.type === "text" ? [b.text] : [])).join("\n").trim() || "(no answer)";
			} catch (e) {
				answer = `Error: ${(e as Error).message}`;
			} finally {
				ctx.ui.setStatus("btw", undefined);
			}

			if (ctx.mode !== "tui") return ctx.ui.notify(answer, "info");
			await showBox(ctx, `btw · ${question}`, new Markdown(answer, 1, 1, getMarkdownTheme()), "not saved to the session");
		},
	});
}
