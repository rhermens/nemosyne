import assert from "node:assert/strict";
import test from "node:test";
import type {
	ExtensionAPI,
	ExtensionContext,
	SessionEntry,
} from "@earendil-works/pi-coding-agent";

import extension, { sessionEvents } from "./index.js";

test("sessionEvents maps successful and failed tool results", () => {
	const entries = [
		{
			type: "message",
			id: "entry-1",
			parentId: null,
			timestamp: "2026-09-17T00:00:00Z",
			message: {
				role: "toolResult",
				toolCallId: "call-1",
				toolName: "read",
				content: [],
				isError: false,
				timestamp: 1_789_603_200_000,
			},
		},
		{
			type: "message",
			id: "entry-2",
			parentId: "entry-1",
			timestamp: "2026-09-17T00:00:01Z",
			message: {
				role: "toolResult",
				toolCallId: "call-2",
				toolName: "bash",
				content: [],
				isError: true,
				timestamp: 1_789_603_201_000,
			},
		},
	] as SessionEntry[];

	assert.deepEqual(sessionEvents(entries), [
		{
			timestamp: "2026-09-17T00:00:00.000Z",
			kind: "tool",
			tool: "read",
			event_outcome: { tag: "Succeeded" },
		},
		{
			timestamp: "2026-09-17T00:00:01.000Z",
			kind: "tool",
			tool: "bash",
			event_outcome: { tag: "Failed", reason: "ToolFailed" },
		},
	]);
});

test("sessionEvents maps user and assistant text messages", () => {
	const entries = [
		{
			type: "message",
			id: "entry-1",
			parentId: null,
			timestamp: "2026-09-17T00:00:00Z",
			message: {
				role: "user",
				content: [{ type: "text", text: "Please inspect the session." }],
				timestamp: 1_789_603_200_000,
			},
		},
		{
			type: "message",
			id: "entry-2",
			parentId: "entry-1",
			timestamp: "2026-09-17T00:00:01Z",
			message: {
				role: "assistant",
				content: [
					{ type: "thinking", thinking: "internal reasoning" },
					{ type: "text", text: "The session is healthy." },
					{ type: "text", text: "No action is required." },
				],
				timestamp: 1_789_603_201_000,
			},
		},
	] as SessionEntry[];

	assert.deepEqual(sessionEvents(entries), [
		{
			timestamp: "2026-09-17T00:00:00.000Z",
			kind: "message",
			role: "user",
			content: "Please inspect the session.",
		},
		{
			timestamp: "2026-09-17T00:00:01.000Z",
			kind: "message",
			role: "assistant",
			content: "The session is healthy.\n\nNo action is required.",
		},
	]);
});

test("agent_settled posts the active session branch once per leaf", async () => {
	type SettledHandler = (
		event: unknown,
		ctx: ExtensionContext,
	) => Promise<void>;

	let settledHandler: SettledHandler | undefined;
	const pi = {
		on(event: string, handler: SettledHandler) {
			assert.equal(event, "agent_settled");
			settledHandler = handler;
		},
	} as unknown as ExtensionAPI;
	const context = {
		cwd: "/workspace/project",
		hasUI: false,
		model: { provider: "openai", id: "gpt-5" },
		sessionManager: {
			getSessionId: () => "session-1",
			getLeafId: () => "leaf-1",
			getBranch: () => [],
			buildSessionContext: () => ({ model: null }),
		},
	} as unknown as ExtensionContext;

	let requests = 0;
	let requestBody: unknown;
	const originalFetch = globalThis.fetch;
	globalThis.fetch = async (input, init) => {
		requests += 1;
		assert.equal(String(input), "http://127.0.0.1:9787/sessions");
		requestBody = JSON.parse(String(init?.body));
		return new Response(null, { status: 200 });
	};

	try {
		extension(pi);
		const handler = settledHandler;
		assert.ok(handler);
		await handler({}, context);
		await handler({}, context);
	} finally {
		globalThis.fetch = originalFetch;
	}

	assert.equal(requests, 1);
	assert.deepEqual(requestBody, {
		id: "session-1",
		model: "openai/gpt-5",
		working_directory: "/workspace/project",
		sequence: [],
	});
});
