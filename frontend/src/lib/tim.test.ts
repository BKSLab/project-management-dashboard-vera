import { describe, expect, it } from "vitest";
import { TIM_CHAT_HINT, TIM_NAME, TIM_PERSONA, describePageContext, isForTim, pageContext } from "@/lib/tim";

describe("isForTim — имя в начале и граница слова, как на сервере", () => {
    it.each(["Вера, что горит?", "ВЕРА перенеси срок", "  вера: сводка", "вера!", "Вера", "Вера_сводка", "Вера🙂", "Вера PM, что горит?"])("«%s» — Вере", (text) => {
        expect(isForTim(text)).toBe(true);
    });
    it.each(["Веранда", "Вероника", "Вера2", "ВераO", "Вера𐐀", "Вера²", "коллеги, Вера сказала", "@Вера привет", "Тим, сводка", "ТИМ", "Тим PM, сводка", "", "ве", null, undefined])("«%s» — не Вере", (text) => {
        expect(isForTim(text)).toBe(false);
    });
});

describe("имя агента", () => {
    it("представляет Веру как проектного менеджера и показывает обращение по имени", () => {
        expect(TIM_NAME).toBe("Вера");
        expect(TIM_PERSONA).toBe("Вера — проектный менеджер");
        expect(TIM_CHAT_HINT).toContain("Вера, …");
        expect(isForTim("Вера, что горит?")).toBe(true);
        expect(isForTim(`${TIM_NAME}, что горит?`)).toBe(true);
    });
});

describe("pageContext", () => {
    it("берёт проект из адреса и открытую задачу", () => {
        expect(pageContext("/projects/DEMO/board", "", 12)).toEqual({ route: "/projects/DEMO/board", project_key: "DEMO", task_id: 12 });
    });
    it("задачу из ?task=, «new» — не проект", () => {
        expect(pageContext("/my-tasks", "?task=7", null)).toMatchObject({ project_key: null, task_id: 7 });
        expect(pageContext("/projects/new", "", null).project_key).toBeNull();
        expect(pageContext("/projects/DEMO", "?task=abc", null).task_id).toBeNull();
    });
});

describe("контекст доски", () => {
    it("передаёт только выбранную доску со страницы холста", () => {
        expect(pageContext("/boards", "?board=12", null)).toMatchObject({board_id: 12});
        expect(pageContext("/projects/DEMO/whiteboard", "?board=3", null)).toMatchObject({board_id: 3, project_key: "DEMO"});
        expect(pageContext("/my-tasks", "?board=12", null)).not.toHaveProperty("board_id");
        expect(pageContext("/boards", "?board=-1", null)).not.toHaveProperty("board_id");
        expect(describePageContext({route: "/boards", project_key: null, task_id: null, board_id: 12})).toBe("Доска #12");
    });
});

describe("describePageContext", () => {
    it("подписывает проект и задачу", () => {
        expect(describePageContext({ route: "/", project_key: "DEMO", task_id: 12 }, { taskKey: "DEMO-12" })).toBe("Проект DEMO · задача DEMO-12");
        expect(describePageContext({ route: "/", project_key: null, task_id: 12 })).toBe("Задача #12");
        expect(describePageContext({ route: "/", project_key: null, task_id: null })).toBe("");
    });
});

it("не роняет помощника на ошибочной escape-последовательности URL", () => {
    expect(pageContext("/projects/%invalid", "", null).project_key).toBe("%invalid");
});
