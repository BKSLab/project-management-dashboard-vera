import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { LogIn } from "lucide-react";
import { useLogin } from "@/lib/useAuth";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field, Input } from "@/components/ui/Field";
import { ErrorMessage } from "@/components/ui/States";

interface LocationState {
    from?: string;
}

export function LoginPage() {
    const navigate = useNavigate();
    const location = useLocation();
    const login = useLogin();
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");

    const from = (location.state as LocationState | null)?.from ?? "/";
    const canSubmit = username.trim() !== "" && password !== "" && !login.isPending;

    function submit() {
        if (!canSubmit) {
            return;
        }
        login.mutate(
            { username: username.trim(), password },
            { onSuccess: () => navigate(from, { replace: true }) },
        );
    }

    return (
        <div className="flex min-h-screen items-center justify-center bg-app px-4 py-10">
            <div className="flex w-full max-w-sm flex-col gap-5">
                <header className="flex flex-col gap-1 text-center">
                    <h1 className="text-lg font-semibold text-primary">Task Tracker</h1>
                    <p className="text-[13px] text-muted">Войдите, чтобы продолжить работу</p>
                </header>

                <Card className="p-5">
                    <form
                        className="flex flex-col gap-4"
                        onSubmit={(event) => {
                            event.preventDefault();
                            submit();
                        }}
                    >
                        {login.error && (
                            <ErrorMessage
                                title="Не удалось войти"
                                message={(login.error as Error).message}
                            />
                        )}

                        <Field label="Логин">
                            {(id) => (
                                <Input
                                    id={id}
                                    autoFocus
                                    autoComplete="username"
                                    value={username}
                                    onChange={(event) => setUsername(event.target.value)}
                                />
                            )}
                        </Field>

                        <Field label="Пароль">
                            {(id) => (
                                <Input
                                    id={id}
                                    type="password"
                                    autoComplete="current-password"
                                    value={password}
                                    onChange={(event) => setPassword(event.target.value)}
                                />
                            )}
                        </Field>

                        <Button
                            type="submit"
                            variant="primary"
                            size="lg"
                            icon={<LogIn size={15} />}
                            disabled={!canSubmit}
                        >
                            Войти
                        </Button>
                    </form>
                </Card>

                <p className="text-center text-[13px] text-muted">
                    Нет учётной записи?{" "}
                    <Link to="/register" className="text-accent hover:text-accent-hover">
                        Зарегистрироваться
                    </Link>
                </p>
            </div>
        </div>
    );
}
