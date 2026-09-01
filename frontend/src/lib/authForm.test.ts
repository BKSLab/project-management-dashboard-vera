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
    middleName: "   ",
    email: "boris@example.com",
    inviteCode: " код ",
};

describe("validateRegisterForm", () => {
    it("принимает заполненную форму", () => {
        expect(validateRegisterForm({ ...VALID, username: "boris" })).toEqual({});
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

    it("не требует отчество и контакты", () => {
        const errors = validateRegisterForm({
            ...VALID,
            username: "boris",
            middleName: "",
            email: "",
            phone: "",
            telegram: "",
        });

        expect(errors).toEqual({});
    });

    it("замечает опечатку в почте", () => {
        expect(validateRegisterForm({ ...VALID, email: "boris.example.com" }).email).toBeDefined();
    });
});

describe("isRegisterFormValid", () => {
    it("отражает наличие ошибок", () => {
        expect(isRegisterFormValid({ ...VALID, username: "boris" })).toBe(true);
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

    it("превращает пустые необязательные поля в null", () => {
        const payload = toRegisterPayload(VALID);

        expect(payload.middle_name).toBeNull();
        expect(payload.phone).toBeNull();
        expect(payload.telegram).toBeNull();
        expect(payload.email).toBe("boris@example.com");
    });
});
