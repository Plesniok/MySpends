import { ArrowRight, ChartNoAxesColumnIncreasing, Package, ReceiptText, WalletCards } from "lucide-react";
import type { Category, Product, Receipt } from "../types";
import { categoryTone, formatDate, formatMoney, statusLabels } from "../utils";

interface DashboardProps {
  receipts: Receipt[];
  products: Product[];
  categories: Category[];
  onOpenReceipt: (receipt: Receipt) => void;
  onShowReceipts: () => void;
}

export function Dashboard({ receipts, products, categories, onOpenReceipt, onShowReceipts }: DashboardProps) {
  const now = new Date();
  const monthlyReceipts = receipts.filter((receipt) => {
    const date = new Date(receipt.purchased_at || receipt.created_at);
    return date.getMonth() === now.getMonth() && date.getFullYear() === now.getFullYear();
  });
  const monthlyTotal = monthlyReceipts.reduce((sum, receipt) => sum + (receipt.total_grosze || 0), 0);
  const average = monthlyReceipts.length ? Math.round(monthlyTotal / monthlyReceipts.length) : 0;
  const categoryById = new Map(categories.map((category) => [category.id, category]));
  const categoryTotals = new Map<string, number>();
  monthlyReceipts.forEach((receipt) => receipt.items.forEach((item) => {
    const categoryName = item.category_id ? categoryById.get(item.category_id)?.name : undefined;
    const key = categoryName || "Bez kategorii";
    categoryTotals.set(key, (categoryTotals.get(key) || 0) + item.total_price_grosze);
  }));
  const categoryRanking = [...categoryTotals.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);
  const maxCategory = categoryRanking[0]?.[1] || 1;

  return (
    <div className="view-stack">
      <section className="welcome-row">
        <div>
          <span className="eyebrow">Przegląd finansów</span>
          <h1>Twoje wydatki, bez przepisywania.</h1>
          <p>Paragony czytane lokalnie przez AI i uporządkowane w jednym miejscu.</p>
        </div>
        <div className="month-chip">{new Intl.DateTimeFormat("pl-PL", { month: "long", year: "numeric" }).format(now)}</div>
      </section>

      <section className="stats-grid">
        <div className="stat-card stat-primary">
          <span className="stat-icon"><WalletCards size={21} /></span>
          <div><span>Wydatki w tym miesiącu</span><strong>{formatMoney(monthlyTotal)}</strong></div>
          <small>{monthlyReceipts.length} {monthlyReceipts.length === 1 ? "paragon" : "paragonów"}</small>
        </div>
        <div className="stat-card">
          <span className="stat-icon pale-mint"><ReceiptText size={21} /></span>
          <div><span>Wszystkie paragony</span><strong>{receipts.length}</strong></div>
          <small>{receipts.filter((receipt) => receipt.status === "completed").length} odczytanych poprawnie</small>
        </div>
        <div className="stat-card">
          <span className="stat-icon pale-violet"><Package size={21} /></span>
          <div><span>Rozpoznane produkty</span><strong>{products.length}</strong></div>
          <small>{categories.length} dostępnych kategorii</small>
        </div>
        <div className="stat-card">
          <span className="stat-icon pale-amber"><ChartNoAxesColumnIncreasing size={21} /></span>
          <div><span>Średni paragon</span><strong>{formatMoney(average)}</strong></div>
          <small>dla bieżącego miesiąca</small>
        </div>
      </section>

      <section className="dashboard-grid">
        <div className="panel recent-panel">
          <div className="panel-heading">
            <div><span className="eyebrow">Ostatnia aktywność</span><h2>Najnowsze paragony</h2></div>
            <button className="text-link" onClick={onShowReceipts}>Zobacz wszystkie <ArrowRight size={16} /></button>
          </div>
          {receipts.length === 0 ? (
            <div className="dashboard-empty"><ReceiptText size={28} /><strong>Nie masz jeszcze paragonów</strong><span>Dodaj pierwszy plik przyciskiem u góry.</span></div>
          ) : (
            <div className="recent-list">
              {receipts.slice(0, 5).map((receipt) => {
                const status = statusLabels[receipt.status];
                return (
                  <button className="recent-receipt" key={receipt.id} onClick={() => onOpenReceipt(receipt)}>
                    <span className="receipt-avatar"><ReceiptText size={19} /></span>
                    <span className="recent-main"><strong>{receipt.merchant || "Nieznany sklep"}</strong><small>{formatDate(receipt.purchased_at || receipt.created_at)} · {receipt.items.length} pozycji</small></span>
                    <span className={`status-dot dot-${status.tone}`} title={status.label} />
                    <strong className="recent-amount">{formatMoney(receipt.total_grosze, receipt.currency)}</strong>
                    <ArrowRight className="row-arrow" size={17} />
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div className="panel category-panel">
          <div className="panel-heading"><div><span className="eyebrow">Ten miesiąc</span><h2>Według kategorii</h2></div></div>
          {categoryRanking.length === 0 ? (
            <div className="dashboard-empty compact-empty"><ChartNoAxesColumnIncreasing size={27} /><span>Kategorie pojawią się po dodaniu paragonu.</span></div>
          ) : (
            <div className="category-bars">
              {categoryRanking.map(([name, total]) => (
                <div className="category-bar-row" key={name}>
                  <div><span className={`category-dot tone-${categoryTone(name)}`} /><strong>{name}</strong><span>{formatMoney(total)}</span></div>
                  <div className="bar-track"><span className={`bar-fill tone-${categoryTone(name)}`} style={{ width: `${Math.max(8, total / maxCategory * 100)}%` }} /></div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
