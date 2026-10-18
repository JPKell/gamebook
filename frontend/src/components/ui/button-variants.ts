import { cva } from 'class-variance-authority'

export const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 cursor-pointer',
  {
    variants: {
      variant: {
        default: 'bg-accent text-accent-fg hover:bg-accent/90',
        outline: 'border border-border bg-surface hover:bg-surface-2',
        ghost: 'text-muted hover:bg-surface-2 hover:text-text',
      },
      size: {
        sm: 'h-7 px-2.5 text-xs',
        md: 'h-8 px-3',
        icon: 'size-8',
      },
    },
    defaultVariants: { variant: 'default', size: 'md' },
  },
)
