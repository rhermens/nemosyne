import type {
	ExtensionAPI,
	ExtensionContext,
	SessionEntry,
} from "@earendil-works/pi-coding-agent";

const DEFAULT_NEMOSYNE_URL = "http://127.0.0.1:9787";
const REQUEST_TIMEOUT_MS = 5_000;

interface SucceededOutcome {
	tag: "Succeeded";
}

interface FailedOutcome {
	tag: "Failed";
	reason: "ToolFailed";
}

interface ToolEvent {
	timestamp: string;
	kind: "tool";
	tool: string;
	event_outcome: SucceededOutcome | FailedOutcome;
}

interface MessageEvent {
	timestamp: string;
	kind: "message";
	role: "user" | "assistant";
	content: string;
}

type SessionEvent = ToolEvent | MessageEvent;

interface SessionPayload {
	id: string;
	model: string;
	working_directory: string;
	sequence: SessionEvent[];
}

function messageText(content: unknown): string {
	if (typeof content === "string") return content;
	if (!Array.isArray(content)) return "";

	return content
		.flatMap((block) =>
			typeof block === "object" &&
			block !== null &&
			"type" in block &&
			block.type === "text" &&
			"text" in block &&
			typeof block.text === "string"
				? [block.text]
				: [],
		)
		.join("\n\n");
}

export function sessionEvents(entries: SessionEntry[]): SessionEvent[] {
	return entries.flatMap<SessionEvent>((entry) => {
		if (entry.type !== "message") return [];

		const { message } = entry;
		if (message.role === "toolResult") {
			return [
				{
					timestamp: new Date(message.timestamp).toISOString(),
					kind: "tool" as const,
					tool: message.toolName,
					event_outcome: message.isError
						? ({ tag: "Failed", reason: "ToolFailed" } as const)
						: ({ tag: "Succeeded" } as const),
				},
			];
		}

		if (message.role !== "user" && message.role !== "assistant") return [];
		const content = messageText(message.content);
		if (!content) return [];

		return [
			{
				timestamp: new Date(message.timestamp).toISOString(),
				kind: "message" as const,
				role: message.role,
				content,
			},
		];
	});
}

function endpointUrl(): URL {
	const baseUrl = process.env.NEMOSYNE_URL ?? DEFAULT_NEMOSYNE_URL;
	return new URL("sessions", baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`);
}

function sessionModel(ctx: ExtensionContext): string {
	if (ctx.model) {
		return `${ctx.model.provider}/${ctx.model.id}`;
	}

	const branch = ctx.sessionManager.getBranch();
	for (let index = branch.length - 1; index >= 0; index -= 1) {
		const entry = branch[index];
		if (entry?.type === "model_change") {
			return `${entry.provider}/${entry.modelId}`;
		}
	}

	return "unknown";
}

export function sessionPayload(ctx: ExtensionContext): SessionPayload {
	return {
		id: ctx.sessionManager.getSessionId(),
		model: sessionModel(ctx),
		working_directory: ctx.cwd,
		sequence: sessionEvents(ctx.sessionManager.getBranch()),
	};
}

async function storeSession(ctx: ExtensionContext): Promise<void> {
	const response = await fetch(endpointUrl(), {
		method: "POST",
		headers: { "content-type": "application/json" },
		body: JSON.stringify(sessionPayload(ctx)),
		signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
	});

	if (!response.ok) {
		const details = (await response.text()).slice(0, 500);
		throw new Error(
			`Nemosyne returned HTTP ${response.status}${details ? `: ${details}` : ""}`,
		);
	}
}

export default function (pi: ExtensionAPI) {
	let storedLeafId: string | null | undefined;

	pi.on("agent_settled", async (_event, ctx) => {
		const leafId = ctx.sessionManager.getLeafId();
		if (leafId === storedLeafId) return;

		try {
			await storeSession(ctx);
			storedLeafId = leafId;
		} catch (error) {
			const message = error instanceof Error ? error.message : String(error);
			if (ctx.hasUI) {
				ctx.ui.notify(`Could not store session: ${message}`, "warning");
			}
		}
	});
}
