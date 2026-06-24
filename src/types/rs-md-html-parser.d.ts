declare module 'rs-md-html-parser' {
  /**
   * Walks the rendered DOM, computes A4 page boundaries, inserts
   * `.rs-line-split` separator elements at page break points, and sets
   * `data-pages="<n>"` on the root node.
   *
   * @param domNode The root element containing the rendered resume HTML.
   * @returns void (mutates the DOM in place).
   */
  export default function htmlParser(domNode: HTMLElement): void
}
