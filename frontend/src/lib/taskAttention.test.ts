// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { attentionBadges, connectTaskAttention, isAttentionSnapshot } from "./taskAttention";

const snapshot = { new_tasks: 1, overdue_tasks: 1, updated_tasks: 0, total: 1, items: [{ task_id: 1, revision: 1, deadline_revision: 1, overdue: true, is_new: true, is_overdue: true, is_updated: false }] };

class Socket {
    onmessage: ((event: { data: string }) => void) | null = null;
    onclose: ((event: { code: number }) => void) | null = null;
    onopen: (() => void) | null = null;
    onerror: (() => void) | null = null;
    send = vi.fn();
    close = vi.fn();
    message(value: unknown) { this.onmessage?.({ data: JSON.stringify(value) }); }
}

afterEach(() => vi.useRealTimers());

describe("персональные счётчики задач", () => {
    it("сохраняет общий unique total и передаёт нули для сброса встройки", () => {
        expect(attentionBadges(snapshot)).toEqual({ tasks: 1, tasks_new: 1, tasks_overdue: 1, tasks_updated: 0 });
        expect(attentionBadges({ ...snapshot, new_tasks: 0, overdue_tasks: 0, total: 0 })).toEqual({ tasks: 0, tasks_new: 0, tasks_overdue: 0, tasks_updated: 0 });
    });
    it("не принимает некорректные снимки", () => {
        expect(isAttentionSnapshot(snapshot)).toBe(true);
        expect(isAttentionSnapshot({ ...snapshot, total: -1 })).toBe(false);
        expect(isAttentionSnapshot({ ...snapshot, items: [{}] })).toBe(false);
    });
    it("принимает полный snapshot, отвечает heartbeat и переподключается", () => {
        vi.useFakeTimers();
        const sockets: Socket[] = [];
        const received = vi.fn();
        const status = vi.fn();
        const stop = connectTaskAttention({
            createSocket: () => { const s = new Socket(); sockets.push(s); return s as unknown as WebSocket; },
            onSnapshot: received, onStatus: status,
        });
        sockets[0].message({ type: "ping" });
        expect(sockets[0].send).toHaveBeenCalledWith('{"type":"pong"}');
        sockets[0].message({ type: "task-attention", data: snapshot });
        expect(received).toHaveBeenCalledWith(snapshot);
        expect(status).toHaveBeenLastCalledWith("connected");
        sockets[0].onclose?.({ code: 1013 });
        vi.advanceTimersByTime(1000);
        expect(sockets).toHaveLength(2);
        sockets[1].message({ type: "task-attention", data: { ...snapshot, total: 0 } });
        expect(received).toHaveBeenCalledTimes(2);
        stop();
        vi.advanceTimersByTime(100_000);
        expect(sockets).toHaveLength(2);
    });
});
