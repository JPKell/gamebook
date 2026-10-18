import {
  type InputHTMLAttributes,
  type KeyboardEvent,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from 'react'

import { cn } from '@/lib/utils'

import { controlClass } from './field'

/**
 * Local edit state that follows the server value while the user isn't editing.
 * Prevents a background refetch from clobbering in-progress typing.
 */
function useDraft<T>(value: T) {
  const [draft, setDraftState] = useState(value)
  const [editing, setEditing] = useState(false)
  // Follow the server value whenever the user isn't mid-edit.
  const [seen, setSeen] = useState(value)
  if (!editing && value !== seen) {
    setSeen(value)
    setDraftState(value)
  }
  return {
    draft,
    /** User typed: hold local state until done(). */
    edit: (v: T) => {
      setEditing(true)
      setDraftState(v)
    },
    /** Editing finished (commit or cancel). */
    done: () => setEditing(false),
    /** Revert to the server value. */
    revert: () => {
      setEditing(false)
      setDraftState(value)
    },
  }
}

type TextInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'value' | 'onChange'> & {
  value: string
  /** Called on blur/Enter when the value changed. */
  onCommit: (value: string) => void
}

/** Text input that commits on blur or Enter; Escape reverts. */
export function TextInput({ value, onCommit, className, onKeyDown, ...rest }: TextInputProps) {
  const { draft, edit, done, revert } = useDraft(value)
  const skipCommit = useRef(false)
  // Unsaved typing is committed if the field unmounts (e.g. selection changes).
  const pending = useRef<{ draft: string; value: string; onCommit: (v: string) => void } | null>(
    null,
  )
  useLayoutEffect(() => {
    if (pending.current) pending.current = { draft, value, onCommit }
  })
  useEffect(
    () => () => {
      const p = pending.current
      if (p && p.draft !== p.value) p.onCommit(p.draft)
    },
    [],
  )
  const commit = () => {
    pending.current = null
    done()
    if (skipCommit.current) {
      skipCommit.current = false
      return
    }
    if (draft !== value) onCommit(draft)
  }
  return (
    <input
      {...rest}
      value={draft}
      onChange={(e) => {
        pending.current = { draft: e.target.value, value, onCommit }
        edit(e.target.value)
      }}
      onBlur={commit}
      onKeyDown={(e: KeyboardEvent<HTMLInputElement>) => {
        if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
        if (e.key === 'Escape') {
          skipCommit.current = true
          pending.current = null
          revert()
          ;(e.target as HTMLInputElement).blur()
        }
        onKeyDown?.(e)
      }}
      className={cn(controlClass, className)}
    />
  )
}

type NumberInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'value' | 'onChange'> & {
  value: number | null
  onCommit: (value: number | null) => void
  allowEmpty?: boolean
}

export function NumberInput({
  value,
  onCommit,
  allowEmpty = false,
  className,
  ...rest
}: NumberInputProps) {
  const { draft, edit, done, revert } = useDraft(value === null ? '' : String(value))
  const commit = () => {
    if (draft.trim() === '') {
      if (allowEmpty && value !== null) {
        done()
        onCommit(null)
      } else revert()
      return
    }
    const n = Number(draft)
    if (!Number.isFinite(n)) return revert()
    done()
    if (n !== value) onCommit(n)
  }
  return (
    <input
      {...rest}
      type="number"
      inputMode="numeric"
      value={draft}
      onChange={(e) => edit(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
      }}
      className={cn(controlClass, 'tabular-nums', className)}
    />
  )
}

type TextAreaProps = Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, 'value' | 'onChange'> & {
  value: string
  onCommit: (value: string) => void
  /** Autosave after this many ms of inactivity (also saves on blur). */
  debounceMs?: number
}

/** Auto-growing textarea that autosaves after a pause and on blur. */
export function TextArea({ value, onCommit, debounceMs = 800, className, ...rest }: TextAreaProps) {
  const { draft, edit, done } = useDraft(value)
  const ref = useRef<HTMLTextAreaElement>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const latest = useRef({ draft, value, onCommit })
  useLayoutEffect(() => {
    latest.current = { draft, value, onCommit }
  })

  const flush = () => {
    if (timer.current) clearTimeout(timer.current)
    timer.current = null
    const { draft: d, value: v, onCommit: commit } = latest.current
    if (d !== v) commit(d)
  }
  // Save pending text when the field unmounts (e.g. switching nodes).
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current)
      const { draft: d, value: v, onCommit: commit } = latest.current
      if (d !== v) commit(d)
    },
    [],
  )

  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight + 2}px`
  }, [draft])

  return (
    <textarea
      {...rest}
      ref={ref}
      value={draft}
      onChange={(e) => {
        edit(e.target.value)
        if (timer.current) clearTimeout(timer.current)
        timer.current = setTimeout(flush, debounceMs)
      }}
      onBlur={() => {
        flush()
        done()
      }}
      className={cn(controlClass, 'min-h-16 resize-none leading-relaxed', className)}
    />
  )
}

type SelectProps<T extends string> = Omit<
  SelectHTMLAttributes<HTMLSelectElement>,
  'value' | 'onChange'
> & {
  value: T | null
  onValueChange: (value: T | null) => void
  options: { value: T; label: string; group?: string; disabled?: boolean }[]
  /** Label for the empty choice; omit to disallow empty. */
  placeholder?: string
}

/** Native select (accessible, keyboard-friendly) with optional optgroups. */
export function Select<T extends string>({
  value,
  onValueChange,
  options,
  placeholder,
  className,
  ...rest
}: SelectProps<T>) {
  const groups = new Map<string, typeof options>()
  for (const o of options) {
    const g = o.group ?? ''
    groups.set(g, [...(groups.get(g) ?? []), o])
  }
  const render = (opts: typeof options) =>
    opts.map((o) => (
      <option key={o.value} value={o.value} disabled={o.disabled}>
        {o.label}
      </option>
    ))
  return (
    <select
      {...rest}
      value={value ?? ''}
      onChange={(e) => onValueChange(e.target.value === '' ? null : (e.target.value as T))}
      className={cn(controlClass, 'pr-7', className)}
    >
      {placeholder !== undefined && <option value="">{placeholder}</option>}
      {[...groups.entries()].map(([g, opts]) =>
        g ? (
          <optgroup key={g} label={g}>
            {render(opts)}
          </optgroup>
        ) : (
          render(opts)
        ),
      )}
    </select>
  )
}

export function Checkbox({
  checked,
  onCheckedChange,
  label,
  disabled,
}: {
  checked: boolean
  onCheckedChange: (checked: boolean) => void
  label: string
  disabled?: boolean
}) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2 text-sm select-none">
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onCheckedChange(e.target.checked)}
        className="size-4 accent-[var(--accent)]"
      />
      {label}
    </label>
  )
}
