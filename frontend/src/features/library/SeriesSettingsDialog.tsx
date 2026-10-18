import { useUpdateSeries } from '@/api/mutations'
import type { SeriesOut, StyleGuide } from '@/api/types'
import { Dialog } from '@/components/ui/dialog'
import { Field } from '@/components/ui/field'
import { NumberInput, Select, TextArea, TextInput } from '@/components/ui/inputs'
import { fullStyle } from '@/lib/style'

export function SeriesSettingsDialog({
  series,
  open,
  onOpenChange,
}: {
  series: SeriesOut
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const update = useUpdateSeries()
  const style = fullStyle(series.style)
  const setStyle = (patch: Partial<StyleGuide>) =>
    update.mutate({ id: series.id, style: { ...style, ...patch } })

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Series settings"
      description="Changes save as you go."
      className="w-[min(640px,calc(100vw-2rem))]"
    >
      <div className="space-y-4">
        <Field label="Title">
          {(id) => (
            <TextInput
              id={id}
              value={series.title}
              onCommit={(title) => update.mutate({ id: series.id, title })}
            />
          )}
        </Field>
        <Field label="Description" hint="What this world is about.">
          {(id) => (
            <TextArea
              id={id}
              value={series.description}
              onCommit={(description) => update.mutate({ id: series.id, description })}
            />
          )}
        </Field>

        <h3 className="pt-2 text-sm font-semibold">Style guide</h3>
        <p className="-mt-3 text-xs text-muted">
          Every prose draft follows this. Books and nodes can override it.
        </p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Field label="Point of view">
            {(id) => (
              <Select
                id={id}
                value={style.pov}
                onValueChange={(pov) => pov && setStyle({ pov })}
                options={[
                  { value: 'second', label: 'Second (you)' },
                  { value: 'first', label: 'First (I)' },
                  { value: 'third', label: 'Third' },
                ]}
              />
            )}
          </Field>
          <Field label="Tense">
            {(id) => (
              <Select
                id={id}
                value={style.tense}
                onValueChange={(tense) => tense && setStyle({ tense })}
                options={[
                  { value: 'present', label: 'Present' },
                  { value: 'past', label: 'Past' },
                ]}
              />
            )}
          </Field>
          <Field label="Min words">
            {(id) => (
              <NumberInput
                id={id}
                min={0}
                value={style.word_min}
                onCommit={(n) => setStyle({ word_min: n ?? 0 })}
              />
            )}
          </Field>
          <Field label="Max words">
            {(id) => (
              <NumberInput
                id={id}
                min={0}
                value={style.word_max}
                onCommit={(n) => setStyle({ word_max: n ?? 0 })}
              />
            )}
          </Field>
        </div>
        <Field label="Voice" hint='e.g. "Grim, terse, sensory. No modern idioms."'>
          {(id) => (
            <TextArea id={id} value={style.voice} onCommit={(voice) => setStyle({ voice })} />
          )}
        </Field>
        <Field label="Notes for the writer">
          {(id) => (
            <TextArea id={id} value={style.notes} onCommit={(notes) => setStyle({ notes })} />
          )}
        </Field>
      </div>
    </Dialog>
  )
}
