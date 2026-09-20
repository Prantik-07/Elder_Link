import { useEffect, useRef, useState } from "react";
import { ImagePlus, Pencil, Trash2 } from "lucide-react";
import { Modal } from "./Modal";
import { fileToResizedDataUrl, isSupportedImageFile } from "../lib/imageFile";

const STORAGE_KEY = "elderlink.familyPhoto.v1";
const CAPTION = "Dad & family";
// Shown until the caregiver adds their own photo - a warm illustration, not a
// stand-in for an actual photo of anyone, so it can never be mistaken for one.
const DEFAULT_ILLUSTRATION = "/assets/elder-tea.png";

function readStoredPhoto(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    // Private browsing / disabled storage - fall back to the placeholder.
    return null;
  }
}

export function FamilyPhotoCard() {
  const [photo, setPhoto] = useState<string | null>(() => readStoredPhoto());
  const [modalOpen, setModalOpen] = useState(false);
  const [pendingPreview, setPendingPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!modalOpen) {
      setPendingPreview(null);
      setError(null);
    }
  }, [modalOpen]);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;

    if (!isSupportedImageFile(file)) {
      setError("Please choose a JPG, PNG, or WebP image.");
      return;
    }

    try {
      const dataUrl = await fileToResizedDataUrl(file);
      setPendingPreview(dataUrl);
      setError(null);
    } catch {
      setError("Couldn't read that image. Please try a different file.");
    }
  };

  const save = () => {
    if (!pendingPreview) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, pendingPreview);
    } catch {
      setError("Couldn't save the photo - your browser's storage may be full.");
      return;
    }
    setPhoto(pendingPreview);
    setModalOpen(false);
  };

  const remove = () => {
    try {
      window.localStorage.removeItem(STORAGE_KEY);
    } catch {
      // Nothing to do - worst case the old photo just stays until overwritten.
    }
    setPhoto(null);
    setModalOpen(false);
  };

  const preview = pendingPreview ?? photo;

  return (
    <div className="relative shrink-0">
      <button
        type="button"
        onClick={() => setModalOpen(true)}
        aria-label={photo ? "Edit family photo" : "Add a family photo"}
        className="block w-24 -rotate-3 rounded-[3px] bg-[var(--color-paper)] p-1.5 pb-2.5 text-left shadow-[var(--shadow-panel)] ring-1 ring-black/5 transition-transform hover:-rotate-1 hover:scale-[1.03]"
      >
        <span className="relative block aspect-[4/5] w-full overflow-hidden rounded-[2px] bg-[var(--color-ivory-soft)]">
          <img
            src={photo ?? DEFAULT_ILLUSTRATION}
            alt=""
            className="h-full w-full object-cover"
            style={
              photo
                ? undefined
                : { objectPosition: "50% 20%", opacity: 0.35, filter: "grayscale(60%)" }
            }
          />
          {!photo && (
            <span
              className="absolute inset-0 flex items-center justify-center border-2 border-dashed"
              style={{ borderColor: "var(--color-line)" }}
              aria-hidden="true"
            >
              <span
                className="flex h-7 w-7 items-center justify-center rounded-full"
                style={{ backgroundColor: "var(--color-paper)", color: "var(--color-teal)" }}
              >
                <ImagePlus size={14} strokeWidth={2} />
              </span>
            </span>
          )}
        </span>
        <span className="font-hand mt-0.5 block text-center text-[13px] leading-none text-[var(--color-ink-soft)]">
          {photo ? CAPTION : "add your photo"}
        </span>
      </button>

      <span
        className="absolute -right-2 -bottom-2 flex h-[26px] w-[26px] items-center justify-center rounded-full text-[var(--color-paper)] ring-2 ring-[var(--color-ivory)]"
        style={{ backgroundColor: "var(--color-teal)" }}
        aria-hidden="true"
      >
        <Pencil size={11} strokeWidth={2} />
      </span>

      {modalOpen && (
        <Modal onClose={() => setModalOpen(false)} titleId="family-photo-title" maxWidthClass="max-w-sm">
          <h2 id="family-photo-title" className="font-display text-[19px] text-[var(--color-ink)]">
            Family photo
          </h2>
          <p className="mt-1 text-[13px] leading-snug text-[var(--color-ink-muted)]">
            A personal photo you choose - just for you, shown alongside your care overview. ElderLink
            doesn&rsquo;t identify anyone in it.
          </p>

          <div
            className="relative mt-4 flex aspect-[4/3] w-full items-center justify-center overflow-hidden rounded-xl border"
            style={{
              borderColor: "var(--color-line)",
              backgroundColor: "var(--color-ivory-soft)",
              borderStyle: preview ? "solid" : "dashed",
            }}
          >
            <img
              src={preview ?? DEFAULT_ILLUSTRATION}
              alt={preview ? "Selected family photo preview" : ""}
              className="h-full w-full object-cover"
              style={
                preview
                  ? undefined
                  : { objectPosition: "50% 15%", opacity: 0.35, filter: "grayscale(60%)" }
              }
            />
            {!preview && (
              <span
                className="absolute flex flex-col items-center gap-1.5 text-[var(--color-ink-soft)]"
                aria-hidden="true"
              >
                <span
                  className="flex h-10 w-10 items-center justify-center rounded-full"
                  style={{ backgroundColor: "var(--color-paper)", color: "var(--color-teal)" }}
                >
                  <ImagePlus size={18} strokeWidth={1.75} />
                </span>
              </span>
            )}
          </div>
          {!preview && (
            <p className="mt-1.5 text-[12px] text-[var(--color-ink-muted)]">
              This is just a sample illustration, not a real photo - add your own below.
            </p>
          )}

          {error && (
            <p role="alert" className="mt-2 text-[12.5px]" style={{ color: "var(--color-concern)" }}>
              {error}
            </p>
          )}

          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/jpg,image/png,image/webp"
            onChange={handleFileChange}
            className="sr-only"
          />

          <div className="mt-4 flex flex-wrap items-center gap-2.5">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="rounded-full border px-4 py-2 text-[13px] font-semibold text-[var(--color-ink-soft)] transition-colors hover:text-[var(--color-ink)]"
              style={{ borderColor: "var(--color-line)" }}
            >
              Choose a photo&hellip;
            </button>
            {photo && !pendingPreview && (
              <button
                type="button"
                onClick={remove}
                className="inline-flex items-center gap-1.5 rounded-full px-3 py-2 text-[13px] font-medium text-[var(--color-concern)] transition-opacity hover:opacity-75"
              >
                <Trash2 size={13} aria-hidden="true" />
                Remove
              </button>
            )}
          </div>

          <div className="mt-6 flex gap-2.5 border-t pt-4" style={{ borderColor: "var(--color-line)" }}>
            <button
              type="button"
              onClick={save}
              disabled={!pendingPreview}
              className="rounded-full px-5 py-2.5 text-[13.5px] font-semibold text-[var(--color-paper)] transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
              style={{ backgroundColor: "var(--color-teal)" }}
            >
              Save changes
            </button>
            <button
              type="button"
              onClick={() => setModalOpen(false)}
              className="rounded-full border px-5 py-2.5 text-[13.5px] font-semibold text-[var(--color-ink-soft)]"
              style={{ borderColor: "var(--color-line)" }}
            >
              Cancel
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
