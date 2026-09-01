import type { RegisterPayload } from "@/lib/types";

export const USERNAME_PATTERN = /^[A-Za-z0-9_.-]{3,50}$/;
export const MIN_PASSWORD_LENGTH = 8;

export interface RegisterFormValues {
    username: string;
    password: string;
    passwordConfirm: string;
    lastName: string;
    firstName: string;
    middleName: string;
    email: string;
    phone: string;
    telegram: string;
    inviteCode: string;
}

export const EMPTY_REGISTER_FORM: RegisterFormValues = {
    username: "",
    password: "",
    passwordConfirm: "",
    lastName: "",
    firstName: "",
    middleName: "",
    email: "",
    phone: "",
    telegram: "",
    inviteCode: "",
};

export type RegisterErrors = Partial<Record<keyof RegisterFormValues, string>>;

/**
 * Проверяет форму регистрации до отправки — ради быстрого отклика.
 * Гарантией остаётся сервер: те же правила продублированы в схеме.
 */
export function validateRegisterForm(values: RegisterFormValues): RegisterErrors {
    const errors: RegisterErrors = {};

    if (!USERNAME_PATTERN.test(values.username)) {
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
    if (values.email.trim() !== "" && !values.email.includes("@")) {
        errors.email = "Похоже, в адресе опечатка.";
    }
    return errors;
}

export function isRegisterFormValid(values: RegisterFormValues): boolean {
    return Object.keys(validateRegisterForm(values)).length === 0;
}

/** Готовит тело запроса: пустые необязательные поля уходят как null. */
export function toRegisterPayload(values: RegisterFormValues): RegisterPayload {
    return {
        username: values.username.trim().toLowerCase(),
        password: values.password,
        password_confirm: values.passwordConfirm,
        last_name: values.lastName.trim(),
        first_name: values.firstName.trim(),
        middle_name: values.middleName.trim() || null,
        email: values.email.trim() || null,
        phone: values.phone.trim() || null,
        telegram: values.telegram.trim() || null,
        invite_code: values.inviteCode.trim(),
    };
}
