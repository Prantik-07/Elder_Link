const SUPPORTED_MIME_TYPES = new Set(["image/jpeg", "image/jpg", "image/png", "image/webp"]);

function hasSupportedExtension(name: string): boolean {
  return /\.(jpe?g|png|webp)$/i.test(name);
}

export function isSupportedImageFile(file: File): boolean {
  const type = file.type.toLowerCase();
  if (SUPPORTED_MIME_TYPES.has(type)) return true;
  // Some pickers/OSes hand back an empty MIME type - fall back to the extension.
  return type === "" && hasSupportedExtension(file.name);
}

/**
 * Downscales an image file to a data URL capped at maxDim on its longest
 * side. Keeps what we store in localStorage small (a phone photo can be
 * several MB; a resized JPEG is typically well under 500KB) and avoids
 * hitting the per-origin storage quota.
 */
export async function fileToResizedDataUrl(
  file: File,
  maxDim = 720,
  quality = 0.85,
): Promise<string> {
  const bitmap = await createImageBitmap(file);
  try {
    const scale = Math.min(1, maxDim / Math.max(bitmap.width, bitmap.height));
    const width = Math.max(1, Math.round(bitmap.width * scale));
    const height = Math.max(1, Math.round(bitmap.height * scale));

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Canvas 2D context is not available");
    ctx.drawImage(bitmap, 0, 0, width, height);

    const mime = file.type === "image/png" ? "image/png" : "image/jpeg";
    return canvas.toDataURL(mime, quality);
  } finally {
    bitmap.close();
  }
}
