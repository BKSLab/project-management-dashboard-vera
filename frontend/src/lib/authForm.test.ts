import { describe, expect, it } from "vitest";
import {
    EMPTY_REGISTER_FORM,
    isRegisterFormValid,
    toRegisterPayload,
    validateRegisterForm,
    type RegisterFormValues,
} from "@/lib/authForm";

const VALID: RegisterFormValues = {
    ...EMPTY_REGISTER_FORM,
    username: "  Boris  ",
    password: "pa$$word123",
    passwordConfirm: "pa$$word123",
    lastName: "  Кузнецов  ",
    firstName: "Борис",
    inviteCode: " код ",
};

describe("validateRegisterForm", () => {
    it("принимает заполненную форму", () => {
        expect(validateRegisterForm(VALID)).toEqual({});
    });

    it("требует совпадения паролей", () => {
        const errors = validateRegisterForm({ ...VALID, passwordConfirm: "другой" });

        expect(errors.passwordConfirm).toBe("Пароли не совпадают.");
    });

    it("требует достаточно длинный пароль", () => {
        const errors = validateRegisterForm({ ...VALID, password: "short", passwordConfirm: "short" });

        expect(errors.password).toBeDefined();
    });

    it("проверяет формат логина", () => {
        expect(validateRegisterForm({ ...VALID, username: "ab" }).username).toBeDefined();
        expect(validateRegisterForm({ ...VALID, username: "борис" }).username).toBeDefined();
        expect(validateRegisterForm({ ...VALID, username: "bo ris" }).username).toBeDefined();
    });

    it("требует фамилию, имя и код приглашения", () => {
        const errors = validateRegisterForm({
            ...VALID,
            lastName: "  ",
            firstName: "",
            inviteCode: "",
        });

        expect(errors.lastName).toBeDefined();
        expect(errors.firstName).toBeDefined();
        expect(errors.inviteCode).toBeDefined();
    });

    it("не спрашивает ничего сверх минимума", () => {
        // Форма регистрации собирает ровно шесть полей: остальное — в профиле.
        expect(Object.keys(EMPTY_REGISTER_FORM).sort()).toEqual([
            "firstName",
            "inviteCode",
            "lastName",
            "password",
            "passwordConfirm",
            "username",
        ]);
    });
});

describe("isRegisterFormValid", () => {
    it("отражает наличие ошибок", () => {
        expect(isRegisterFormValid(VALID)).toBe(true);
        expect(isRegisterFormValid(EMPTY_REGISTER_FORM)).toBe(false);
    });
});

describe("toRegisterPayload", () => {
    it("нормализует логин и обрезает строки", () => {
        const payload = toRegisterPayload(VALID);

        expect(payload.username).toBe("boris");
        expect(payload.last_name).toBe("Кузнецов");
        expect(payload.invite_code).toBe("код");
    });

    it("отправляет только поля регистрации", () => {
        expect(Object.keys(toRegisterPayload(VALID)).sort()).toEqual([
            "first_name",
            "invite_code",
            "last_name",
            "password",
            "password_confirm",
            "username",
        ]);
    });
});
