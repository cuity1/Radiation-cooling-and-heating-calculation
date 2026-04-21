import { useMemo, useState, useEffect } from 'react'
import { HelpCircle } from 'lucide-react'
import Modal from '../ui/Modal'
import { MdRenderer } from '../../help/mdRenderer'
import { getHelpDoc, type HelpDocKey } from '../../help/registry'

export default function HelpButton(props: { doc: HelpDocKey; className?: string; size?: 'sm' | 'md' }) {
  const [open, setOpen] = useState(false)
  const [shouldBlink, setShouldBlink] = useState(false)

  useEffect(() => {
    const key = `help_clicked_${props.doc}`
    if (!localStorage.getItem(key)) setShouldBlink(true)
  }, [props.doc])

  const help = useMemo(() => getHelpDoc(props.doc), [props.doc])
  const sizeCls = props.size === 'sm' ? 'h-7 w-7' : 'h-8 w-8'

  const modalWidthClassName = props.doc === 'in_situ_era5' ? 'max-w-3xl' : undefined

  return (
    <>
      <button
        type="button"
        onClick={() => {
          setOpen(true)
          if (shouldBlink) {
            localStorage.setItem(`help_clicked_${props.doc}`, 'true')
            setShouldBlink(false)
          }
        }}
        aria-label="帮助"
        className={
          'inline-flex items-center justify-center rounded-field border border-border bg-bg-elevated text-text-secondary hover:text-text-primary transition-all duration-200 hover:border-border-light ' +
          sizeCls +
          ' ' +
          (props.className ?? '') +
          (shouldBlink ? ' animate-help-blink ring-2 ring-sky-400/80 border-sky-300 bg-sky-400/20' : '')
        }
      >
        <HelpCircle size={15} />
      </button>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={help.title}
        widthClassName={modalWidthClassName}
      >
        <MdRenderer md={help.md} />
      </Modal>
    </>
  )
}
