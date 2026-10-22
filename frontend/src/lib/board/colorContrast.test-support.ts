export type Rgb = { r: number; g: number; b: number }

/** #rgb, #rrggbb → каналы 0..255. Иные записи (rgba, color-mix) не поддерживаются намеренно. */
export function parseHex(color: string): Rgb | null {
  const hex = color.trim().replace(/^#/, '')
  if (!/^[0-9a-fA-F]+$/.test(hex)) return null
  if (hex.length === 3) {
    const [r, g, b] = hex.split('')
    return { r: parseInt(r + r, 16), g: parseInt(g + g, 16), b: parseInt(b + b, 16) }
  }
  if (hex.length === 6) {
    return {
      r: parseInt(hex.slice(0, 2), 16),
      g: parseInt(hex.slice(2, 4), 16),
      b: parseInt(hex.slice(4, 6), 16),
    }
  }
  return null
}

function channel(value: number): number {
  const c = value / 255
  return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)
}

export function relativeLuminance(color: Rgb): number {
  return 0.2126 * channel(color.r) + 0.7152 * channel(color.g) + 0.0722 * channel(color.b)
}

/** Отношение контраста двух непрозрачных цветов: от 1 (не различить) до 21. */
export function contrastRatio(foreground: string, background: string): number {
  const fg = parseHex(foreground)
  const bg = parseHex(background)
  if (!fg || !bg) throw new Error(`Не разобрал цвет: ${foreground} / ${background}`)
  const l1 = relativeLuminance(fg)
  const l2 = relativeLuminance(bg)
  const [light, dark] = l1 >= l2 ? [l1, l2] : [l2, l1]
  return Math.round(((light + 0.05) / (dark + 0.05)) * 100) / 100
}

/** Пороги WCAG AA: текст читают, границу элемента только различают. */
export const MIN_TEXT = 4.5
export const MIN_NON_TEXT = 3.0

/**
 * Достаёт токены одного блока темы из CSS: `--имя: #hex;`.
 * Значения через var()/color-mix/rgba пропускаются — их контраст зависит от фона
 * и считается на своём месте, а не в общем списке.
 */
export function parseThemeTokens(css: string, selector: string): Record<string, string> {
  const start = css.indexOf(selector)
  if (start === -1) throw new Error(`В теме нет блока ${selector}`)
  const open = css.indexOf('{', start)
  const end = css.indexOf('\n}', open)
  // Молча дочитывать до конца файла нельзя: тогда «светлая тема» вберёт в себя токены
  // тёмной, поздние перезапишут ранние, и тест померяет не ту тему, ничего не заметив.
  if (end === -1) throw new Error(`Не нашёл конец блока ${selector} в теме`)
  const block = css.slice(open, end)
  const tokens: Record<string, string> = {}
  for (const [, name, value] of block.matchAll(/--([a-z0-9-]+):\s*(#[0-9a-fA-F]{3,8})\s*;/g)) {
    tokens[name] = value
  }
  return tokens
}

/** Смесь двух непрозрачных цветов в sRGB, как color-mix(in srgb, fg share, bg). */
export function mixHex(foreground: string, background: string, share: number): string {
  const fg = parseHex(foreground)
  const bg = parseHex(background)
  if (!fg || !bg) throw new Error(`Не разобрал цвет: ${foreground} / ${background}`)
  const channelMix = (a: number, b: number) => Math.round(a * share + b * (1 - share)).toString(16).padStart(2, '0')
  return `#${channelMix(fg.r, bg.r)}${channelMix(fg.g, bg.g)}${channelMix(fg.b, bg.b)}`
}

const toLinear = (value: number) => channel(value)
const toGamma = (value: number) => {
  const v = value <= 0.0031308 ? 12.92 * value : 1.055 * Math.pow(value, 1 / 2.4) - 0.055
  return Math.round(Math.min(1, Math.max(0, v)) * 255)
}

/**
 * То же, что делает dataColor() в браузере: oklch(from X clamp(min, l, max) c h).
 * Цвет вне охвата sRGB обрезается по каналам — браузер ужимает насыщенность, результат
 * у него светлее или равен, поэтому замер здесь не оптимистичнее реального.
 */
export function clampOklchLightness(color: string, min: number, max: number): string {
  return clampOklch(color, min, max, Infinity)
}

/**
 * То же, что stickerSurface() в браузере: oklch(from X clamp(min, l, max) min(c, cMax) h) —
 * светлота зажата в пределы темы, насыщенность не выше cMax. Вне охвата sRGB — обрезка по каналам.
 */
export function clampOklch(color: string, min: number, max: number, cMax: number): string {
  const rgb = parseHex(color)
  if (!rgb) throw new Error(`Не разобрал цвет: ${color}`)
  const r = toLinear(rgb.r), g = toLinear(rgb.g), b = toLinear(rgb.b)
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
  const lightness = Math.min(max, Math.max(min, 0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s))
  let a = 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s
  let bb = 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s
  const chroma = Math.hypot(a, bb)
  if (chroma > cMax) {
    a = (a / chroma) * cMax
    bb = (bb / chroma) * cMax
  }
  const l3 = Math.pow(lightness + 0.3963377774 * a + 0.2158037573 * bb, 3)
  const m3 = Math.pow(lightness - 0.1055613458 * a - 0.0638541728 * bb, 3)
  const s3 = Math.pow(lightness - 0.0894841775 * a - 1.291485548 * bb, 3)
  const out = [
    4.0767416621 * l3 - 3.3077115913 * m3 + 0.2309699292 * s3,
    -1.2684380046 * l3 + 2.6097574011 * m3 - 0.3413193965 * s3,
    -0.0041960863 * l3 - 0.7034186147 * m3 + 1.707614701 * s3,
  ].map(toGamma)
  return `#${out.map((v) => v.toString(16).padStart(2, '0')).join('')}`
}

/** Числовой токен темы (`--имя: 0.7;`) — для порогов вроде --data-l-min. */
export function parseThemeNumber(css: string, selector: string, name: string): number {
  const start = css.indexOf(selector)
  if (start === -1) throw new Error(`В теме нет блока ${selector}`)
  const open = css.indexOf('{', start)
  const end = css.indexOf('\n}', open)
  const match = css.slice(open, end).match(new RegExp(`--${name}:\\s*([0-9.]+)\\s*;`))
  if (!match) throw new Error(`В блоке ${selector} нет числового токена --${name}`)
  return Number(match[1])
}
