import type { PageSetup, Placement } from './api'

/**
 * A page at trim size with the bleed (dashed) and the text block (safe area), and
 * the placement's printed box drawn where its size and alignment put it.
 */
export function PagePreview({
  setup,
  placement,
  imageUrl,
  className,
}: {
  setup: PageSetup
  placement?: Pick<Placement, 'layout' | 'print_size'>
  imageUrl?: string | null
  className?: string
}) {
  const b = setup.bleed_mm
  const W = setup.trim_width_mm
  const H = setup.trim_height_mm
  const left = setup.margin_inner_mm + (setup.gutter_mm ?? 0)
  const top = setup.margin_top_mm
  const tw = setup.text_width
  const th = setup.text_height
  let box: { x: number; y: number; w: number; h: number } | null = null
  if (placement) {
    const { layout, print_size: s } = placement
    if (layout.size === 'full_page' && layout.bleed) {
      box = { x: -b, y: -b, w: W + 2 * b, h: H + 2 * b }
    } else if (layout.size === 'full_page') {
      box = {
        x: left + (tw - s.width_mm) / 2,
        y: top + (th - s.height_mm) / 2,
        w: s.width_mm,
        h: s.height_mm,
      }
    } else {
      const x =
        layout.align === 'left'
          ? left
          : layout.align === 'right'
            ? left + tw - s.width_mm
            : left + (tw - s.width_mm) / 2
      box = { x, y: top + 4, w: s.width_mm, h: s.height_mm }
    }
  }
  const lines = Array.from({ length: Math.floor(th / 6) }, (_, i) => top + 3 + i * 6)
  return (
    <svg
      viewBox={`${-b - 2} ${-b - 2} ${W + 2 * b + 4} ${H + 2 * b + 4}`}
      className={className}
      role="img"
      aria-label={`Page preview: ${W} × ${H} mm trim${box ? `, art ${placement!.print_size.width_mm} × ${placement!.print_size.height_mm} mm` : ''}`}
    >
      <rect
        x={-b}
        y={-b}
        width={W + 2 * b}
        height={H + 2 * b}
        fill="none"
        stroke="var(--danger)"
        strokeDasharray="2 2"
        strokeWidth={0.6}
      />
      <rect
        x={0}
        y={0}
        width={W}
        height={H}
        fill="var(--bg)"
        stroke="var(--border)"
        strokeWidth={0.8}
      />
      <rect
        x={left}
        y={top}
        width={tw}
        height={th}
        fill="none"
        stroke="var(--accent)"
        strokeDasharray="1.5 1.5"
        strokeWidth={0.4}
      />
      {lines.map((y) => {
        // Text lines flow around wrapped art and stop above/below anything else.
        let x1 = left
        let x2 = left + tw
        if (box && placement && y >= box.y - 1 && y <= box.y + box.h + 1) {
          const { size, wrap, align, gutter_mm } = placement.layout
          if (size === 'full_page' || !wrap || align === 'center') return null
          if (align === 'left') x1 = box.x + box.w + gutter_mm
          else x2 = box.x - gutter_mm
        }
        return (
          <line key={y} x1={x1} x2={x2} y1={y} y2={y} stroke="var(--border)" strokeWidth={1.2} />
        )
      })}
      {box &&
        (imageUrl ? (
          <image
            href={imageUrl}
            x={box.x}
            y={box.y}
            width={box.w}
            height={box.h}
            preserveAspectRatio="xMidYMid slice"
          />
        ) : (
          <rect
            x={box.x}
            y={box.y}
            width={box.w}
            height={box.h}
            fill="var(--accent)"
            fillOpacity={0.12}
            stroke="var(--accent)"
            strokeWidth={0.6}
          />
        ))}
    </svg>
  )
}
