import { useEffect, useState } from 'react'
import { Html5Qrcode, Html5QrcodeSupportedFormats } from 'html5-qrcode'

export default function CameraScanner({ onDecode }: { onDecode: (text: string) => void }) {
  const [cameraError, setCameraError] = useState(() => {
    if (!window.isSecureContext) {
      return `Le navigateur bloque la caméra pour ${window.location.origin}. Ouvrez l’application depuis http://localhost ou en HTTPS; une adresse IP locale n’est pas considérée comme localhost.`
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      return 'Cette page ne peut pas accéder à l’API caméra. Vérifiez le navigateur et son contexte sécurisé.'
    }
    return ''
  })

  useEffect(() => {
    if (cameraError) return

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
    ).catch((error: unknown) => {
      if (!active) return
      const name = error instanceof DOMException ? error.name : ''
      if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
        setCameraError('Accès caméra refusé. Autorisez la caméra pour ce site dans les paramètres du navigateur, puis rechargez la page.')
      } else if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
        setCameraError('Aucune caméra détectée sur cet appareil.')
      } else if (name === 'NotReadableError' || name === 'TrackStartError') {
        setCameraError('La caméra est utilisée par une autre application. Fermez-la puis réessayez.')
      } else {
        const detail = error instanceof Error ? error.message : String(error)
        setCameraError(`Impossible de démarrer la caméra (${name || 'erreur navigateur'}). Vérifiez la permission et qu’aucune autre application ne l’utilise. ${detail}`)
      }
    })
    return () => {
      active = false
      if (reader.isScanning) void reader.stop().catch(() => undefined)
    }
  }, [cameraError, onDecode])

  return <div><div id="passage-qr-reader" className="mx-auto min-h-24 max-w-sm overflow-hidden rounded-xl bg-slate-900" />{cameraError && <p role="alert" className="mt-2 text-xs text-red-600">{cameraError}</p>}</div>
}
