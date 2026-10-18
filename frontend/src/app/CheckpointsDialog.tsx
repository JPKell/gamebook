import { RotateCcw, Save, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { useQuery } from '@tanstack/react-query'

import { api, unwrap } from '@/api/client'
import { qk } from '@/api/keys'
import { useCreateCheckpoint, useDeleteCheckpoint, useRestoreCheckpoint } from '@/api/mutations'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { controlClass } from '@/components/ui/field'

export function CheckpointsDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const list = useQuery({
    queryKey: qk.checkpoints,
    queryFn: () => unwrap(api.GET('/api/checkpoints')),
    enabled: open,
  })
  const create = useCreateCheckpoint()
  const restore = useRestoreCheckpoint()
  const remove = useDeleteCheckpoint()
  const [name, setName] = useState('')

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Checkpoints"
      description="Snapshots of your whole library. Restoring one replaces everything (a safety checkpoint is saved first)."
    >
      <form
        className="mb-4 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          if (!name.trim()) return
          create.mutate(name.trim(), {
            onSuccess: () => {
              setName('')
              toast('Checkpoint saved')
            },
          })
        }}
      >
        <input
          aria-label="Checkpoint name"
          placeholder="e.g. Before rewriting Act 2"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className={controlClass}
        />
        <Button type="submit" disabled={!name.trim() || create.isPending}>
          <Save className="size-4" /> Save
        </Button>
      </form>
      {list.isPending ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : list.data?.length ? (
        <ul className="divide-y divide-border rounded-lg border border-border">
          {list.data.map((c) => (
            <li key={c.id} className="flex items-center gap-2 px-3 py-2">
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium">{c.name}</div>
                <div className="text-xs text-muted">
                  {new Date(c.created_at).toLocaleString()} · {(c.size / 1024).toFixed(0)} KB
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  if (
                    window.confirm(`Restore “${c.name}”? Everything changes back to that moment.`)
                  )
                    restore.mutate(c.id, {
                      onSuccess: () => toast('Restored. A safety checkpoint was saved first.'),
                    })
                }}
              >
                <RotateCcw className="size-3.5" /> Restore
              </Button>
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Delete ${c.name}`}
                onClick={() => remove.mutate(c.id)}
              >
                <Trash2 className="size-3.5" />
              </Button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted">No checkpoints yet.</p>
      )}
    </Dialog>
  )
}
