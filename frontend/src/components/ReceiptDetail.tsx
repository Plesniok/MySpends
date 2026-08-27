import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  CalendarDays,
  ExternalLink,
  FileImage,
  LoaderCircle,
  MapPin,
  PackageOpen,
  ReceiptText,
  ScanLine,
} from "lucide-react";
import { api } from "../api";
import type { Category, Receipt } from "../types";
import { categoryTone, formatDate, formatMoney, formatQuantity, statusLabels } from "../utils";

interface ReceiptDetailProps {
  receipt: Receipt | null;
  categories: Category[];
  onBack?: () => void;
}

export function ReceiptDetail({ receipt, categories, onBack }: ReceiptDetailProps) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [imageLoading, setImageLoading] = useState(false);
  const [imageError, setImageError] = useState<string | null>(null);

  const categoryById = useMemo(
    () => new Map(categories.map((category) => [category.id, category])),
    [categories],
  );

  useEffect(() => {
    let active = true;
    setImageUrl(null);
    setImageError(null);
    if (!receipt?.image_path) return;
    setImageLoading(true);
    api.imageUrl(receipt.id)
      .then((result) => active && setImageUrl(result.url))
      .catch((reason: unknown) => active && setImageError(reason instanceof Error ? reason.message : "Brak podglądu"))
      .finally(() => active && setImageLoading(false));
    return () => { active = false; };
  }, [receipt?.id, receipt?.image_path]);

  if (!receipt) {
    return (
      <section className="receipt-empty panel">
        <div className="empty-illustration"><ReceiptText size={34} /></div>
        <h3>Wybierz paragon</h3>
        <p>Kliknij paragon z listy, aby zobaczyć produkty i oryginalny plik.</p>
      </section>
    );
  }

  const status = statusLabels[receipt.status];

  return (
    <article className="receipt-detail panel">
      <header className="detail-header">
        <button className="mobile-back" onClick={onBack}><ArrowLeft size={19} /> Wróć</button>
        <div className="detail-heading">
          <div className="merchant-mark"><ReceiptText size={22} /></div>
          <div>
            <div className="detail-title-row">
              <h2>{receipt.merchant || "Nieznany sklep"}</h2>
              <span className={`status-badge status-${status.tone}`}>{status.label}</span>
            </div>
            <div className="detail-meta">
              <span><CalendarDays size={15} /> {formatDate(receipt.purchased_at || receipt.created_at)}</span>
              <span><MapPin size={15} /> {receipt.items.length} pozycji</span>
            </div>
          </div>
        </div>
        <div className="detail-total">
          <span>Razem</span>
          <strong>{formatMoney(receipt.total_grosze, receipt.currency)}</strong>
        </div>
      </header>

      {receipt.processing_error && <div className="error-banner detail-error">{receipt.processing_error}</div>}

      <div className="detail-grid">
        <section className="items-section">
          <div className="section-title">
            <div><span className="eyebrow"><ScanLine size={14} /> Odczyt AI</span><h3>Produkty na paragonie</h3></div>
            <span className="items-count">{receipt.items.length}</span>
          </div>

          {receipt.items.length === 0 ? (
            <div className="inline-empty"><PackageOpen size={28} /><span>Brak rozpoznanych produktów</span></div>
          ) : (
            <>
              <div className="items-table">
                <div className="items-table-head">
                  <span>Produkt</span><span>Ilość</span><span>Cena jedn.</span><span>Wartość</span>
                </div>
                {receipt.items.map((item) => {
                  const category = item.category_id ? categoryById.get(item.category_id) : null;
                  return (
                    <div className="item-row" key={item.id}>
                      <div className="item-name">
                        <strong>{item.normalized_name || item.raw_name}</strong>
                        <span>{item.raw_name}</span>
                        {category && <small className={`category-pill tone-${categoryTone(category.name)}`}>{category.name}</small>}
                      </div>
                      <span>{formatQuantity(item.quantity, item.unit)}</span>
                      <span>{formatMoney(item.unit_price_grosze, receipt.currency)}</span>
                      <strong>{formatMoney(item.total_price_grosze, receipt.currency)}</strong>
                    </div>
                  );
                })}
              </div>

              <div className="mobile-items">
                {receipt.items.map((item) => {
                  const category = item.category_id ? categoryById.get(item.category_id) : null;
                  return (
                    <div className="mobile-item-card" key={item.id}>
                      <div className="mobile-item-main">
                        <div><strong>{item.normalized_name || item.raw_name}</strong><span>{item.raw_name}</span></div>
                        <strong>{formatMoney(item.total_price_grosze, receipt.currency)}</strong>
                      </div>
                      <div className="mobile-item-meta">
                        <span>{formatQuantity(item.quantity, item.unit)} × {formatMoney(item.unit_price_grosze, receipt.currency)}</span>
                        {category && <small className={`category-pill tone-${categoryTone(category.name)}`}>{category.name}</small>}
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </section>

        <aside className="receipt-file-section">
          <div className="section-title compact"><div><span className="eyebrow"><FileImage size={14} /> Plik źródłowy</span><h3>Zdjęcie paragonu</h3></div></div>
          <div className="receipt-image-frame">
            {imageLoading && <div className="image-state"><LoaderCircle className="spin" size={25} /><span>Pobieram podgląd…</span></div>}
            {!imageLoading && imageUrl && <img src={imageUrl} alt={`Paragon ${receipt.merchant || ""}`} />}
            {!imageLoading && imageError && <div className="image-state"><FileImage size={25} /><span>{imageError}</span></div>}
            {!imageLoading && !imageUrl && !imageError && <div className="image-state"><FileImage size={25} /><span>Brak zdjęcia</span></div>}
          </div>
          {imageUrl && (
            <a className="button button-secondary full-width" href={imageUrl} target="_blank" rel="noreferrer">
              <ExternalLink size={17} /> Otwórz oryginalny plik
            </a>
          )}
          <div className="file-security"><span className="security-dot" /> Link prywatny · ważny 15 minut</div>
        </aside>
      </div>
    </article>
  );
}
