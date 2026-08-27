import { Check, Package, Search, Tags } from "lucide-react";
import { useMemo, useState } from "react";
import type { Category, Product, Receipt } from "../types";
import { categoryTone, formatDate, formatMoney } from "../utils";

interface ProductsViewProps {
  products: Product[];
  receipts: Receipt[];
  categories: Category[];
  onCategoryChange: (productId: string, categoryId: string | null) => Promise<void>;
}

export function ProductsView({ products, receipts, categories, onCategoryChange }: ProductsViewProps) {
  const [query, setQuery] = useState("");
  const [savingId, setSavingId] = useState<string | null>(null);
  const usage = useMemo(() => {
    const map = new Map<string, { count: number; total: number; latest: string }>();
    receipts.forEach((receipt) => receipt.items.forEach((item) => {
      if (!item.product_id) return;
      const current = map.get(item.product_id) || { count: 0, total: 0, latest: receipt.purchased_at || receipt.created_at };
      current.count += 1;
      current.total += item.total_price_grosze;
      if (new Date(receipt.purchased_at || receipt.created_at) > new Date(current.latest)) current.latest = receipt.purchased_at || receipt.created_at;
      map.set(item.product_id, current);
    }));
    return map;
  }, [receipts]);
  const filtered = products.filter((product) => product.canonical_name.toLocaleLowerCase("pl").includes(query.trim().toLocaleLowerCase("pl")));

  const updateCategory = async (product: Product, categoryId: string) => {
    setSavingId(product.id);
    try { await onCategoryChange(product.id, categoryId || null); }
    finally { setSavingId(null); }
  };

  return (
    <div className="view-stack">
      <section className="page-title-row">
        <div><span className="eyebrow">Katalog automatyczny</span><h1>Produkty</h1><p>Produkty utworzone na podstawie nazw znalezionych na paragonach.</p></div>
        <div className="products-summary"><span><Package size={20} /></span><div><strong>{products.length}</strong><small>produktów</small></div></div>
      </section>
      <section className="panel products-panel">
        <div className="products-toolbar">
          <label className="search-field"><Search size={18} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Szukaj produktu…" /></label>
          <span className="toolbar-note"><Tags size={16} /> Kategorię możesz poprawić w każdej chwili</span>
        </div>
        {filtered.length === 0 ? (
          <div className="list-empty products-empty"><Package size={30} /><strong>Brak produktów</strong><span>Produkty pojawią się automatycznie po odczytaniu paragonu.</span></div>
        ) : (
          <div className="products-table">
            <div className="products-head"><span>Produkt</span><span>Kategoria</span><span>Wystąpienia</span><span>Łączne wydatki</span><span>Ostatni zakup</span></div>
            {filtered.map((product) => {
              const stats = usage.get(product.id);
              const category = categories.find((item) => item.id === product.category_id);
              return (
                <div className="product-row" key={product.id}>
                  <div className="product-identity"><span className={`product-icon tone-${categoryTone(category?.name || product.canonical_name)}`}><Package size={18} /></span><strong>{product.canonical_name}</strong></div>
                  <div className="category-select-wrap">
                    <span className={`category-dot tone-${categoryTone(category?.name || "Bez kategorii")}`} />
                    <select value={product.category_id || ""} onChange={(event) => void updateCategory(product, event.target.value)} disabled={savingId === product.id}>
                      <option value="">Bez kategorii</option>
                      {categories.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}
                    </select>
                    {savingId === product.id ? <span className="mini-loader" /> : <Check className="saved-check" size={15} />}
                  </div>
                  <span>{stats?.count || 0}</span>
                  <strong>{formatMoney(stats?.total || 0)}</strong>
                  <span>{stats ? formatDate(stats.latest) : "—"}</span>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
