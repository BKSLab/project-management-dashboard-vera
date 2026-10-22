/** Русское склонение существительного при числе: plural(3, "риск", "риска", "рисков") → «риска». */
export function plural(count: number, one: string, few: string, many: string): string {
    const mod100 = Math.abs(count) % 100;
    const mod10 = mod100 % 10;
    if (mod100 >= 11 && mod100 <= 14) return many;
    if (mod10 === 1) return one;
    if (mod10 >= 2 && mod10 <= 4) return few;
    return many;
}
