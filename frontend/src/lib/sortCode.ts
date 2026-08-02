export function compareWbsCode(a: string, b: string): number {
    const segmentsA = a.split(".").map(Number);
    const segmentsB = b.split(".").map(Number);
    const length = Math.max(segmentsA.length, segmentsB.length);

    for (let i = 0; i < length; i++) {
        const partA = segmentsA[i] ?? 0;
        const partB = segmentsB[i] ?? 0;
        if (partA !== partB) return partA - partB;
    }
    return 0;
}
