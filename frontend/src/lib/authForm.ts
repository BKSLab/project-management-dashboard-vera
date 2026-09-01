import type { RegisterPayload } from "@/lib/types";

export const USERNAME_PATTERN = /^[A-Za-z0-9_.-]{3,50}$/;
export const MIN_PASSWORD_LENGTH = 8;

/**
 * Поля регистрации: только необходимый минимум. Отчество и контакты
 * заполняются позже в профиле, чтобы не удлинять вход в сервис.
 */
export interface RegisterFormValues {
    username: string;
    password: string;
    passwordConfirm: string;
    lastName: string;
    firstName: string;
    inviteCode: string;
}

export const EMPTY_REGISTER_FORM: RegisterFormValues = {
    username: "",
    password: "",
    passwordConfirm: "",
    lastName: "",
    firstName: "",
    inviteCode: "",
};

export type RegisterErrors = Partial<Record<keyof RegisterFormValues, string>>;

/**
 * Проверяет форму регистрации до отправки — ради быстрого отклика.
 * Гарантией остаётся сервер: те же правила продублированы в схеме.
 */
export function validateRegisterForm(values: RegisterFormValues): RegisterErrors {
    const errors: RegisterErrors = {};

    if (!USERNAME_PATTERN.test(values.username.trim())) {
        errors.username = "Латиница, цифры, точка, дефис и подчёркивание, от 3 до 50 символов.";
    }
    if (values.password.length < MIN_PASSWORD_LENGTH) {
        errors.password = `Не короче ${MIN_PASSWORD_LENGTH} символов.`;
    }
    if (values.passwordConfirm !== values.password) {
        errors.passwordConfirm = "Пароли не совпадают.";
    }
    if (values.lastName.trim() === "") {
        errors.lastName = "Укажите фамилию.";
    }
    if (values.firstName.trim() === "") {
        errors.firstName = "Укажите имя.";
    }
    if (values.inviteCode.trim() === "") {
        errors.inviteCode = "Регистрация доступна по коду приглашения.";
    }
    return errors;
}

export function isRegisterFormValid(values: RegisterFormValues): boolean {
    return Object.keys(validateRegisterForm(values)).length === 0;
}

export function toRegisterPayload(values: RegisterFormValues): RegisterPayload {
    return {
        username: values.username.trim().toLowerCase(),
        password: values.password,
        password_confirm: values.passwordConfirm,
        last_name: values.lastName.trim(),
        first_name: values.firstName.trim(),
        invite_code: values.inviteCode.trim(),
    };
}
