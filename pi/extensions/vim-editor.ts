// Vim-style modal editing, like editorMode "vim" in Claude Code. Esc: normal mode; i/a: insert.
// Adapted from pi's examples/extensions/modal-editor.ts, with w, b, dd, D and u added.
// Also renames Claude Code slash commands to pi's built-ins on submit (pi has no alias setting),
// and adds Claude Code's /color, which tints the prompt box for the session.
import { CustomEditor, type ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { getTerminalColorMode, matchesKey, rgbColor, styleText, truncateToWidth, visibleWidth } from "@earendil-works/pi-tui";

const NORMAL_KEYS: Record<string, string> = {
	h: "\x1b[D",
	j: "\x1b[B",
	k: "\x1b[A",
	l: "\x1b[C",
	"0": "\x01",
	$: "\x05",
	x: "\x1b[3~",
	w: "\x1bf",
	b: "\x1bb",
	D: "\x0b",
	u: "\x1f",
};

const ALIASES: Record<string, string> = {
	rewind: "tree",
	clear: "new",
	branch: "fork",
	rename: "name",
	config: "settings",
	status: "session",
	cost: "session",
	context: "session",
	usage: "session",
	effort: "thinking",
	review: "code-review",
	help: "hotkeys",
	exit: "quit",
};

// Claude Code's /color names, as 24-bit colors.
const COLORS: Record<string, [number, number, number]> = {
	red: [230, 80, 80],
	orange: [240, 150, 60],
	yellow: [230, 200, 70],
	green: [90, 190, 110],
	cyan: [80, 200, 210],
	blue: [90, 140, 240],
	purple: [170, 110, 230],
	pink: [235, 120, 180],
};
const CHOICES = [...Object.keys(COLORS), "default"];
let color: string | undefined;

function alias(text: string): string {
	const m = text.trim().match(/^\/(\S+)(.*)$/s);
	const target = m && ALIASES[m[1]!];
	return target ? `/${target}${m![2]}` : text;
}

class ModalEditor extends CustomEditor {
	private mode: "normal" | "insert" = "insert";
	private pending = "";

	constructor(...args: ConstructorParameters<typeof CustomEditor>) {
		super(...args);
		let submit: ((text: string) => void) | undefined;
		Object.defineProperty(this, "onSubmit", {
			get: () => submit && ((text: string) => submit!(alias(text))),
			set: (fn) => (submit = fn),
		});
		// pi repaints the border on every thinking-level change; a /color choice wins over it.
		let border = (s: string) => s;
		Object.defineProperty(this, "borderColor", {
			get: () => {
				const rgb = color && COLORS[color];
				return rgb ? (s: string) => styleText(s, { fg: rgbColor(...rgb) }, getTerminalColorMode()) : border;
			},
			set: (fn) => (border = fn),
		});
	}

	handleInput(data: string): void {
		if (matchesKey(data, "escape")) {
			if (this.mode === "insert") {
				this.mode = "normal";
			} else {
				super.handleInput(data);
			}
			return;
		}

		if (this.mode === "insert") {
			super.handleInput(data);
			return;
		}

		// dd: clear the line
		if (data === "d") {
			if (this.pending === "d") {
				super.handleInput("\x01");
				super.handleInput("\x0b");
				this.pending = "";
			} else this.pending = "d";
			return;
		}
		this.pending = "";

		if (data === "i" || data === "a") {
			this.mode = "insert";
			if (data === "a") super.handleInput("\x1b[C");
			return;
		}
		if (data in NORMAL_KEYS) {
			super.handleInput(NORMAL_KEYS[data]);
			return;
		}

		if (data.length === 1 && data.charCodeAt(0) >= 32) return;
		super.handleInput(data);
	}

	render(width: number): string[] {
		const lines = super.render(width);
		if (lines.length === 0) return lines;

		const label = this.mode === "normal" ? " NORMAL " : " INSERT ";
		const last = lines.length - 1;
		if (visibleWidth(lines[last]!) >= label.length) {
			lines[last] = truncateToWidth(lines[last]!, width - label.length, "") + label;
		}
		return lines;
	}
}

export default function (pi: ExtensionAPI) {
	for (const [name, target] of Object.entries(ALIASES)) {
		pi.registerCommand(name, { description: `Alias for /${target}`, handler: async () => {} });
	}
	pi.registerCommand("color", {
		description: `Set the prompt bar color for this session: ${CHOICES.join("|")}`,
		getArgumentCompletions: (prefix: string) =>
			CHOICES.filter((c) => c.startsWith(prefix)).map((c) => ({ value: c, label: c })),
		handler: async (args, ctx) => {
			const name = args.trim().toLowerCase();
			if (!CHOICES.includes(name)) {
				ctx.ui.notify(`Colors: ${CHOICES.join(", ")}`, "warning");
				return;
			}
			color = name === "default" ? undefined : name;
			pi.appendEntry("color", { color });
		},
	});
	pi.on("session_start", (_event, ctx) => {
		color = undefined;
		for (const e of ctx.sessionManager.getEntries()) {
			if (e.type === "custom" && e.customType === "color") color = (e.data as { color?: string })?.color;
		}
		ctx.ui.setEditorComponent((tui, theme, kb) => new ModalEditor(tui, theme, kb));
	});
}
