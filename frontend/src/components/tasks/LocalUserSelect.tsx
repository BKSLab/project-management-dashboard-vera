import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, endpoints, queryKeys } from "@/lib/api";
import type { UserSummary } from "@/lib/types";
import { fullName } from "@/lib/types";
import { Popover } from "@/components/ui/Popover";
import { Input } from "@/components/ui/Field";

export function LocalUserSelect({ label, selected, onChange, multiple = false, disabled = false }: {
    label: string; selected: UserSummary[]; onChange: (users: UserSummary[]) => void; multiple?: boolean; disabled?: boolean;
}) {
    const [search, setSearch] = useState("");
    const users = useQuery({ queryKey: queryKeys.users(search), queryFn: () => api.get<UserSummary[]>(endpoints.users(search)), staleTime: 30_000 });
    const choices = [...new Map([...selected, ...(users.data ?? [])].map(user => [user.id, user])).values()];
    return <Popover label={label} align="start" disabled={disabled} triggerClassName="w-full justify-start font-normal"
        trigger={selected.length ? selected.map(fullName).join(", ") : "Не выбраны"}>
        {({ close }) => <div className="flex flex-col gap-2">
            <Input aria-label={`Поиск: ${label}`} value={search} placeholder="Имя или логин" onChange={event => setSearch(event.target.value)} />
            {users.error && <p role="alert" className="text-xs text-danger">Не удалось загрузить пользователей.</p>}
            <div className="max-h-56 overflow-y-auto">
                {!multiple && <button type="button" className="w-full rounded-control p-2 text-left text-sm text-muted hover:bg-surface" onClick={() => { onChange([]); close(); }}>Не назначен</button>}
                {choices.map(user => <button key={user.id} type="button" aria-pressed={selected.some(item => item.id === user.id)}
                    className="flex w-full items-center gap-2 rounded-control p-2 text-left text-[13px] text-secondary hover:bg-surface"
                    onClick={() => { onChange(multiple ? selected.some(item => item.id === user.id) ? selected.filter(item => item.id !== user.id) : [...selected, user] : [user]); if (!multiple) close(); }}>
                    <span>{multiple && (selected.some(item => item.id === user.id) ? "☑ " : "☐ ")}{fullName(user)}<span className="block text-[11px] text-muted">@{user.username}</span></span>
                </button>)}
                {users.data?.length === 0 && <p className="p-2 text-xs text-muted">Пользователь не найден.</p>}
            </div>
        </div>}
    </Popover>;
}
