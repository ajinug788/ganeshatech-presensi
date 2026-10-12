// compress.js — resize sisi terpanjang ≤1280px, JPEG quality 0.78
export async function compressBlob(blob) {
  if (blob.size < 200_000) return blob; // sudah kecil
  const bmp = await createImageBitmap(blob);
  const scale = Math.min(1, 1280 / Math.max(bmp.width, bmp.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bmp.width * scale);
  canvas.height = Math.round(bmp.height * scale);
  canvas.getContext('2d').drawImage(bmp, 0, 0, canvas.width, canvas.height);
  return new Promise(resolve => canvas.toBlob(b => resolve(b || blob), 'image/jpeg', 0.78));
}
