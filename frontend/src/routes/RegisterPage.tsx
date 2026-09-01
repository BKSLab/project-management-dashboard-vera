import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { UserPlus } from "lucide-react";
import {
    EMPTY_REGISTER_FORM,
    isRegisterFormValid,
    toRegisterPayload,
    validateRegisterForm,
    type RegisterFormValues,
} from "@/lib/authForm";
import { useRegister } from "@/lib/useAuth";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field, Input } from "@/components/ui/Field";
import { ErrorMessage } from "@/components/ui/States";

export function RegisterPage() {
    const navigate = useNavigate();
    const register = useRegister();
    const [values, setValues] = useState<RegisterFormValues>(EMPTY_REGISTER_FORM);
    const [touched, setTouched] = useState(false);

    const errors = validateRegisterForm(values);
    const showError = (field: keyof RegisterFormValues) => (touched ? errors[field] : undefined);

    function update(patch: Partial<RegisterFormValues>) {
        setValues({ ...values, ...patch });
    }

    function submit() {
        setTouched(true);
        if (!isRegisterFormValid(values) || register.isPending) {
            return;
        }
        register.mutate(toRegisterPayload(values), {
            onSuccess: () => navigate("/", { replace: true }),
        });
    }

    return (
        <div className="flex min-h-screen items-center justify-center bg-app px-4 py-10">
            <div className="flex w-full max-w-lg flex-col gap-5">
                <header className="flex flex-col gap-1 text-center">
                    <h1 className="text-lg font-semibold text-primary">Регистрация</h1>
                    <p className="text-[13px] text-muted">
                        Нужен код приглашения: регистрация закрыта для посторонних
                    </p>
                </header>

                <Card className="p-5">
                    <form
                        className="flex flex-col gap-4"
                        onSubmit={(event) => {
                            event.preventDefault();
                            submit();
                        }}
                    >
                        {register.error && (
                            <ErrorMessage
                                title="Не удалось зарегистрироваться"
                                message={(register.error as Error).message}
                            />
                        )}

                        <div className="grid gap-4 sm:grid-cols-2">
                            <Field label="Логин" error={showError("username")}>
                                {(id) => (
                                    <Input
                                        id={id}
                                        autoFocus
                                        autoComplete="username"
                                        placeholder="boris"
                                        value={values.username}
                                        onChange={(event) => update({ username: event.target.value })}
                                    />
                                )}
                            </Field>

                            <Field label="Код приглашения" error={showError("inviteCode")}>
                                {(id) => (
                                    <Input
                                        id={id}
                                        value={values.inviteCode}
                                        onChange={(event) =>
                                            update({ inviteCode: event.target.value })
                                        }
                                    />
                                )}
                            </Field>

                            <Field
                                label="Пароль"
                                hint="Не короче 8 символов"
                                error={showError("password")}
                            >
                                {(id) => (
                                    <Input
                                        id={id}
                                        type="password"
                                        autoComplete="new-password"
                                        value={values.password}
                                        onChange={(event) => update({ password: event.target.value })}
                                    />
                                )}
                            </Field>

                            <Field label="Повторите пароль" error={showError("passwordConfirm")}>
                                {(id) => (
                                    <Input
                                        id={id}
                                        type="password"
                                        autoComplete="new-password"
                                        value={values.passwordConfirm}
                                        onChange={(event) =>
                                            update({ passwordConfirm: event.target.value })
                                        }
                                    />
                                )}
                            </Field>
                        </div>

                        <div className="grid gap-4 border-t border-line-subtle pt-4 sm:grid-cols-2">
                            <Field label="Фамилия" error={showError("lastName")}>
                                {(id) => (
                                    <Input
                                        id={id}
                                        value={values.lastName}
                                        onChange={(event) => update({ lastName: event.target.value })}
                                    />
                                )}
                            </Field>

                            <Field label="Имя" error={showError("firstName")}>
                                {(id) => (
                                    <Input
                                        id={id}
                                        value={values.firstName}
                                        onChange={(event) =>
                                            update({ firstName: event.target.value })
                                        }
                                    />
                                )}
                            </Field>

                            <Field label="Отчество" hint="Необязательно">
                                {(id) => (
                                    <Input
                                        id={id}
                                        value={values.middleName}
                                        onChange={(event) =>
                                            update({ middleName: event.target.value })
                                        }
                                    />
                                )}
                            </Field>

                            <Field label="Почта" hint="Необязательно" error={showError("email")}>
                                {(id) => (
                                    <Input
                                        id={id}
                                        type="email"
                                        autoComplete="email"
                                        value={values.email}
                                        onChange={(event) => update({ email: event.target.value })}
                                    />
                                )}
                            </Field>

                            <Field label="Телефон" hint="Необязательно">
                                {(id) => (
                                    <Input
                                        id={id}
                                        value={values.phone}
                                        onChange={(event) => update({ phone: event.target.value })}
                                    />
                                )}
                            </Field>

                            <Field label="Telegram" hint="Необязательно">
                                {(id) => (
                                    <Input
                                        id={id}
                                        placeholder="@boris"
                                        value={values.telegram}
                                        onChange={(event) => update({ telegram: event.target.value })}
                                    />
                                )}
                            </Field>
                        </div>

                        <Button
                            type="submit"
                            variant="primary"
                            size="lg"
                            icon={<UserPlus size={15} />}
                            disabled={register.isPending}
                        >
                            Зарегистрироваться
                        </Button>
                    </form>
                </Card>

                <p className="text-center text-[13px] text-muted">
                    Уже есть учётная запись?{" "}
                    <Link to="/login" className="text-accent hover:text-accent-hover">
                        Войти
                    </Link>
                </p>
            </div>
        </div>
    );
}
