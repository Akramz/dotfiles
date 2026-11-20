// A bordered box that closes on Enter or Esc, shared by /btw and /diff. No index.ts here, so pi
// does not load this folder as an extension.
import { DynamicBorder, type ExtensionCommandContext } from "@earendil-works/pi-coding-agent";
import { type Component, Container, matchesKey, Text } from "@earendil-works/pi-tui";

export async function showBox(ctx: ExtensionCommandContext, title: string, body: Component, hint: string) {
	await ctx.ui.custom((_tui, theme, _kb, done) => {
		const box = new Container();
		const border = new DynamicBorder((s: string) => theme.fg("accent", s));
		box.addChild(border);
		box.addChild(new Text(theme.fg("accent", theme.bold(title)), 1, 0));
		box.addChild(body);
		box.addChild(new Text(theme.fg("dim", `Esc or Enter to close · ${hint}`), 1, 0));
		box.addChild(border);
		return {
			render: (w: number) => box.render(w),
			invalidate: () => box.invalidate(),
			handleInput: (d: string) => {
				if (matchesKey(d, "enter") || matchesKey(d, "escape")) done(undefined);
			},
		};
	});
}
