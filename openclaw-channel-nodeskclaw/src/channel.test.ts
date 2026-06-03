import { describe, expect, it } from "vitest";
import { nodeskclawPlugin } from "./channel.js";

describe("nodeskclaw channel plugin", () => {
  it("declares broadcast as a group-capable target", async () => {
    expect(nodeskclawPlugin.capabilities.chatTypes).toContain("direct");
    expect(nodeskclawPlugin.capabilities.chatTypes).toContain("group");
    expect(nodeskclawPlugin.messaging?.inferTargetChatType?.({ to: "broadcast" })).toBe("group");
    expect(nodeskclawPlugin.messaging?.inferTargetChatType?.({ to: "agent:Alice" })).toBeUndefined();
  });

  it("lists the office broadcast group without changing peer lookup", async () => {
    const cfg = {};

    const groups = await nodeskclawPlugin.directory?.listGroups?.({
      cfg,
      query: "办公室",
      limit: 10,
      runtime: {},
    });
    expect(groups).toEqual([{ kind: "group", id: "broadcast", name: "办公室群聊" }]);

    const limitedGroups = await nodeskclawPlugin.directory?.listGroups?.({
      cfg,
      query: "missing",
      limit: 1,
      runtime: {},
    });
    expect(limitedGroups).toEqual([]);

    const peers = await nodeskclawPlugin.directory?.listPeers?.({
      cfg,
      query: "broadcast",
      limit: 10,
      runtime: {},
    });
    expect(peers).toEqual([]);
  });
});
