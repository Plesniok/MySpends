import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { CheckCircle2, FileImage, LoaderCircle, Sparkles, Upload, X } from "lucide-react";
import type { Receipt } from "../types";

interface UploadModalProps {
  open: boolean;
  onClose: () => void;
  onUpload: (file: File) => Promise<Receipt>;
}

const acceptedTypes = ["image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"];

export function UploadModal({ open, onClose, onUpload }: UploadModalProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!file) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  useEffect(() => {
    if (!open) {
      setFile(null);
      setError(null);
      setDragging(false);
    }
  }, [open]);

  if (!open) return null;

  const chooseFile = (nextFile?: File) => {
    if (!nextFile) return;
    if (!acceptedTypes.includes(nextFile.type)) {
      setError("Wybierz zdjęcie JPEG, PNG, WebP, HEIC lub HEIF.");
      return;
    }
    if (nextFile.size > 10 * 1024 * 1024) {
      setError("Plik może mieć maksymalnie 10 MB.");
      return;
    }
    setError(null);
    setFile(nextFile);
  };

  const handleInput = (event: ChangeEvent<HTMLInputElement>) => chooseFile(event.target.files?.[0]);
  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    chooseFile(event.dataTransfer.files?.[0]);
  };

  const submit = async () => {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      await onUpload(file);
      onClose();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Nie udało się przetworzyć paragonu.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="modal-backdrop" onMouseDown={() => !uploading && onClose()}>
      <section className="upload-modal" onMouseDown={(event) => event.stopPropagation()} aria-modal="true">
        <header className="modal-header">
          <div>
            <span className="eyebrow"><Sparkles size={14} /> Analiza lokalnym AI</span>
            <h2>Dodaj nowy paragon</h2>
            <p>Wystarczy jedno czytelne zdjęcie — resztę uzupełnimy automatycznie.</p>
          </div>
          <button className="icon-button" onClick={onClose} disabled={uploading} aria-label="Zamknij">
            <X size={20} />
          </button>
        </header>

        {!file ? (
          <div
            className={`dropzone ${dragging ? "is-dragging" : ""}`}
            onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
          >
            <div className="dropzone-icon"><Upload size={28} /></div>
            <strong>Przeciągnij tutaj zdjęcie</strong>
            <span>lub kliknij, aby wybrać plik</span>
            <small>JPEG, PNG, WebP, HEIC · maks. 10 MB</small>
          </div>
        ) : (
          <div className="selected-file">
            <div className="file-preview">
              {preview && <img src={preview} alt="Podgląd wybranego paragonu" />}
            </div>
            <div className="file-details">
              <span className="file-type-icon"><FileImage size={20} /></span>
              <div>
                <strong>{file.name}</strong>
                <span>{(file.size / 1024 / 1024).toFixed(2)} MB</span>
              </div>
              {!uploading && (
                <button className="text-button" onClick={() => setFile(null)}>Zmień</button>
              )}
            </div>
          </div>
        )}

        <div className="ai-checklist">
          <span><CheckCircle2 size={16} /> sklep i data</span>
          <span><CheckCircle2 size={16} /> produkty i ilości</span>
          <span><CheckCircle2 size={16} /> ceny i kategorie</span>
        </div>

        {uploading && (
          <div className="processing-note">
            <LoaderCircle className="spin" size={20} />
            <div><strong>Wysyłam paragon…</strong><span>Analiza AI rozpocznie się w tle.</span></div>
          </div>
        )}
        {error && <div className="error-banner">{error}</div>}

        <footer className="modal-actions">
          <button className="button button-ghost" onClick={onClose} disabled={uploading}>Anuluj</button>
          <button className="button button-primary" onClick={submit} disabled={!file || uploading}>
            {uploading ? <><LoaderCircle className="spin" size={18} /> Wysyłam…</> : <><Sparkles size={18} /> Dodaj i odczytaj</>}
          </button>
        </footer>
        <input ref={inputRef} type="file" accept={acceptedTypes.join(",")} onChange={handleInput} hidden />
      </section>
    </div>
  );
}
