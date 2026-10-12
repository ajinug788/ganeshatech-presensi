// camera.js — kamera depan via getUserMedia, fallback <input type="file" capture="user">
export async function startCamera(videoEl) {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 1280 } },
      audio: false,
    });
    videoEl.srcObject = stream;
    await videoEl.play();
    return { ok: true };
  } catch (err) {
    return { ok: false, error: err, fallbackNeeded: err.name === 'NotFoundError' || err.name === 'NotAllowedError' };
  }
}

export function stopCamera(videoEl) {
  const stream = videoEl?.srcObject;
  if (stream) stream.getTracks().forEach(t => t.stop());
  videoEl.srcObject = null;
}

export function captureFrame(videoEl) {
  const canvas = document.createElement('canvas');
  canvas.width = videoEl.videoWidth;
  canvas.height = videoEl.videoHeight;
  canvas.getContext('2d').drawImage(videoEl, 0, 0);
  return new Promise(resolve => canvas.toBlob(b => resolve(b), 'image/jpeg', 0.9));
}
