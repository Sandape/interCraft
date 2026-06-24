/**
 * `#{color}` runtime color token plugin.
 * Ported from 木及简历 (D:\Project\react-resume-site\src\utils\plugins.ts).
 *
 * Post-render regex replace: swaps the literal token `#{color}` in the
 * rendered HTML with the current accent color hex (stripped of `#`).
 * Lets users write `<span style="color: #{color}">` in their markdown and
 * have it auto-follow the color picker.
 */

export interface ColorPluginParams {
  color: string
}

export function colorPlugin(html: string, params: ColorPluginParams): string {
  const hex = params?.color ?? ''
  return html.replace(/#\{color\}/g, hex)
}
