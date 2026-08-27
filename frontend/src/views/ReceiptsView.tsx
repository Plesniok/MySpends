import { CalendarDays, ChevronRight, ReceiptText, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { ReceiptDetail } from "../components/ReceiptDetail";
import type { Category, Receipt } from "../types";
import { formatDate, formatMoney, statusLabels } from "../utils";

interface ReceiptsViewProps {
  receipts: Receipt[];
  categories: Category[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}

export function ReceiptsView({ receipts, categories, selectedId, onSelect }: ReceiptsViewProps) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("pl");
    if (!normalized) return receipts;
    return receipts.filter((receipt) =>
      receipt.merchant?.toLocaleLowerCase("pl").includes(normalized)
      || receipt.items.some((item) => (item.normalized_name || item.raw_name).toLocaleLowerCase("pl").includes(normalized)),
    );
  }, [query, receipts]);
  const selected = receipts.find((receipt) => receipt.id === selectedId) || null;

  return (
    <div className={`receipts-layout ${selected ? "has-mobile-selection" : ""}`}>
      <section className="receipts-list-panel panel">
        <div className="list-header">
          <div><span className="eyebrow">Dokumenty</span><h1>Twoje paragony</h1><p>{receipts.length} plików w bibliotece</p></div>
        </div>
        <label className="search-field"><Search size={18} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Szukaj sklepu lub produktu…" /></label>
        <div className="receipts-list">
          {filtered.length === 0 ? (
            <div className="list-empty"><ReceiptText size={29} /><strong>Brak wyników</strong><span>Zmień wyszukiwaną frazę.</span></div>
          ) : filtered.map((receipt) => {
            const status = statusLabels[receipt.status];
            return (
              <button className={`receipt-list-card ${receipt.id === selectedId ? "is-active" : ""}`} key={receipt.id} onClick={() => onSelect(receipt.id)}>
                <span className="receipt-avatar"><ReceiptText size={19} /></span>
                <span className="receipt-list-main">
                  <span><strong>{receipt.merchant || "Nieznany sklep"}</strong><b>{formatMoney(receipt.total_grosze, receipt.currency)}</b></span>
                  <small><CalendarDays size={13} /> {formatDate(receipt.purchased_at || receipt.created_at)} <i>·</i> {receipt.items.length} pozycji</small>
                  <em className={`status-badge status-${status.tone}`}>{status.label}</em>
                </span>
                <ChevronRight size={18} />
              </button>
            );
          })}
        </div>
      </section>
      <ReceiptDetail receipt={selected} categories={categories} onBack={() => onSelect(null)} />
    </div>
  );
}
