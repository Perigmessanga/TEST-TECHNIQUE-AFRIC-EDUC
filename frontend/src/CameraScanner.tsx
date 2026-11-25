import { useEffect, useState } from 'react'
import { Html5Qrcode, Html5QrcodeSupportedFormats } from 'html5-qrcode'

export default function CameraScanner({ onDecode }: { onDecode: (text: string) => void }) {
  const [cameraError, setCameraError] = useState('')

  useEffect(() => {
    const reader = new Html5Qrcode('passage-qr-reader', {
      formatsToSupport: [Html5QrcodeSupportedFormats.QR_CODE],
      verbose: false,
    })
    let active = true
    reader.start(
      { facingMode: 'environment' },
      { fps: 10, qrbox: { width: 230, height: 230 } },
      (text) => { if (active) onDecode(text) },
      () => undefined,
    ).catch(() => {
      if (active) setCameraError('Caméra indisponible : vérifiez la permission et utilisez HTTPS ou localhost.')
    })
    return () => {
      active = false
      if (reader.isScanning) void reader.stop().catch(() => undefined)
    }
  }, [onDecode])

  return <div><div id="passage-qr-reader" className="mx-auto min-h-24 max-w-sm overflow-hidden rounded-xl bg-slate-900" />{cameraError && <p role="alert" className="mt-2 text-xs text-red-600">{cameraError}</p>}</div>
}
