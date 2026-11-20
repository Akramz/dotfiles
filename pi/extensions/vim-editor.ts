// Vim-style modal editing, like editorMode "vim" in Claude Code. Esc: normal mode; i/a: insert.
// Adapted from pi's examples/extensions/modal-editor.ts, with w, b, dd, D and u added.
import { CustomEditor, type ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { matchesKey, truncateToWidth, visibleWidth } from "@earendil-works/pi-tui";

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

class ModalEditor extends CustomEditor {
	private mode: "normal" | "insert" = "insert";
	private pending = "";

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
	pi.on("session_start", (_event, ctx) => {
		ctx.ui.setEditorComponent((tui, theme, kb) => new ModalEditor(tui, theme, kb));
	});
}
