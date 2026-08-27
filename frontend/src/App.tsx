import { useCallback, useEffect, useState } from "react";
import {
  CheckCircle2,
  LayoutDashboard,
  Menu,
  PackageSearch,
  Plus,
  ReceiptText,
  RefreshCw,
  Settings,
  Sparkles,
  Wifi,
  WifiOff,
  X,
} from "lucide-react";
import { api, getStoredToken, saveToken } from "./api";
import { UploadModal } from "./components/UploadModal";
import type { Category, Product, Receipt } from "./types";
import { Dashboard } from "./views/Dashboard";
import { ProductsView } from "./views/ProductsView";
import { ReceiptsView } from "./views/ReceiptsView";

type View = "dashboard" | "receipts" | "products";

const navigation: Array<{ id: View; label: string; icon: typeof LayoutDashboard }> = [
  { id: "dashboard", label: "Pulpit", icon: LayoutDashboard },
  { id: "receipts", label: "Paragony", icon: ReceiptText },
  { id: "products", label: "Produkty", icon: PackageSearch },
];

export default function App() {
  const [view, setView] = useState<View>("dashboard");
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedReceiptId, setSelectedReceiptId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const loadData = useCallback(async (showLoader = true) => {
    if (showLoader) setLoading(true);
    setLoadError(null);
    try {
      const [nextReceipts, nextProducts, nextCategories] = await Promise.all([
        api.receipts(), api.products(), api.categories(),
      ]);
      setReceipts(nextReceipts);
      setProducts(nextProducts);
      setCategories(nextCategories);
    } catch (reason) {
      setLoadError(reason instanceof Error ? reason.message : "Nie udało się połączyć z backendem.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void loadData(); }, [loadData]);

  const processingReceiptIds = receipts
    .filter((receipt) => receipt.status === "processing")
    .map((receipt) => receipt.id)
    .sort()
    .join(",");

  useEffect(() => {
    if (!processingReceiptIds) return;

    const receiptIds = processingReceiptIds.split(",");
    let active = true;

    const refreshProcessingReceipts = async () => {
      const results = await Promise.allSettled(receiptIds.map((receiptId) => api.receipt(receiptId)));
      if (!active) return;

      const updatedReceipts = results.flatMap((result) =>
        result.status === "fulfilled" ? [result.value] : [],
      );
      if (!updatedReceipts.length) return;

      const updatesById = new Map(updatedReceipts.map((receipt) => [receipt.id, receipt]));
      setReceipts((current) => current.map((receipt) => updatesById.get(receipt.id) ?? receipt));

      const finishedReceipts = updatedReceipts.filter((receipt) => receipt.status !== "processing");
      if (!finishedReceipts.length) return;

      const [nextProducts, nextCategories] = await Promise.all([api.products(), api.categories()]);
      if (!active) return;
      setProducts(nextProducts);
      setCategories(nextCategories);
      setToast(
        finishedReceipts.some((receipt) => receipt.status === "failed")
          ? "Nie udało się przeanalizować paragonu. Sprawdź szczegóły."
          : "Analiza paragonu została zakończona.",
      );
    };

    void refreshProcessingReceipts();
    const interval = window.setInterval(() => void refreshProcessingReceipts(), 3000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [processingReceiptIds]);

  useEffect(() => {
    if (!toast) return;
    const timeout = window.setTimeout(() => setToast(null), 3500);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  const changeView = (nextView: View) => {
    setView(nextView);
    setMobileMenuOpen(false);
  };

  const openReceipt = (receipt: Receipt) => {
    setSelectedReceiptId(receipt.id);
    setView("receipts");
  };

  const uploadReceipt = async (file: File) => {
    const receipt = await api.uploadReceipt(file);
    setReceipts((current) => [receipt, ...current.filter((item) => item.id !== receipt.id)]);
    setSelectedReceiptId(receipt.id);
    setView("receipts");
    setToast("Paragon przyjęty. AI analizuje go w tle.");
    return receipt;
  };

  const updateProductCategory = async (productId: string, categoryId: string | null) => {
    const updated = await api.updateProductCategory(productId, categoryId);
    setProducts((current) => current.map((product) => product.id === updated.id ? updated : product));
    setReceipts((current) => current.map((receipt) => ({
      ...receipt,
      items: receipt.items.map((item) => item.product_id === productId ? { ...item, category_id: categoryId } : item),
    })));
    setToast("Kategoria produktu została zaktualizowana.");
  };

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileMenuOpen ? "mobile-open" : ""}`}>
        <div className="brand">
          <span className="brand-mark"><ReceiptText size={23} /></span>
          <div><strong>MySpends</strong><small>smart receipts</small></div>
          <button className="sidebar-close" onClick={() => setMobileMenuOpen(false)}><X size={20} /></button>
        </div>

        <button className="sidebar-upload" onClick={() => { setUploadOpen(true); setMobileMenuOpen(false); }}>
          <Plus size={19} /> Dodaj paragon
        </button>

        <nav className="side-nav" aria-label="Główna nawigacja">
          <span className="nav-caption">Przestrzeń</span>
          {navigation.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.id} className={view === item.id ? "active" : ""} onClick={() => changeView(item.id)}>
                <Icon size={19} /><span>{item.label}</span>
                {item.id === "receipts" && receipts.length > 0 && <b>{receipts.length}</b>}
              </button>
            );
          })}
        </nav>

        <div className="ai-card">
          <span className="ai-card-icon"><Sparkles size={19} /></span>
          <div><strong>Lokalne AI</strong><span>Qwen3-VL analizuje dane na Twoim urządzeniu.</span></div>
          <small><span /> Prywatnie i lokalnie</small>
        </div>

        <div className="sidebar-bottom">
          <button onClick={() => setSettingsOpen(true)}><Settings size={18} /> Ustawienia API</button>
          <div className={`connection-state ${loadError ? "offline" : ""}`}>
            {loadError ? <WifiOff size={15} /> : <Wifi size={15} />}
            {loadError ? "Brak połączenia" : "Backend połączony"}
          </div>
        </div>
      </aside>
      {mobileMenuOpen && <div className="mobile-menu-backdrop" onClick={() => setMobileMenuOpen(false)} />}

      <main className="main-area">
        <header className="topbar">
          <button className="mobile-menu-button" onClick={() => setMobileMenuOpen(true)} aria-label="Otwórz menu"><Menu size={22} /></button>
          <div className="mobile-brand"><span className="brand-mark"><ReceiptText size={20} /></span><strong>MySpends</strong></div>
          <div className="topbar-context">
            <span>{navigation.find((item) => item.id === view)?.label}</span>
            <small>Wydatki uporządkowane przez AI</small>
          </div>
          <div className="topbar-actions">
            <button className="icon-button refresh-button" onClick={() => void loadData(false)} aria-label="Odśwież"><RefreshCw size={18} /></button>
            <button className="button button-primary top-upload" onClick={() => setUploadOpen(true)}><Plus size={18} /> Dodaj paragon</button>
          </div>
        </header>

        <div className="content-area">
          {loading ? (
            <div className="page-loader"><span className="loader-logo"><ReceiptText size={28} /></span><strong>Ładuję Twoje wydatki…</strong><span className="loading-line" /></div>
          ) : loadError ? (
            <div className="connection-error panel">
              <span className="error-icon"><WifiOff size={27} /></span>
              <h2>Nie mogę połączyć się z API</h2>
              <p>{loadError}</p>
              <button className="button button-primary" onClick={() => void loadData()}><RefreshCw size={17} /> Spróbuj ponownie</button>
              <button className="text-button" onClick={() => setSettingsOpen(true)}>Ustaw token dostępu</button>
            </div>
          ) : (
            <>
              {view === "dashboard" && <Dashboard receipts={receipts} products={products} categories={categories} onOpenReceipt={openReceipt} onShowReceipts={() => changeView("receipts")} />}
              {view === "receipts" && <ReceiptsView receipts={receipts} categories={categories} selectedId={selectedReceiptId} onSelect={setSelectedReceiptId} />}
              {view === "products" && <ProductsView products={products} receipts={receipts} categories={categories} onCategoryChange={updateProductCategory} />}
            </>
          )}
        </div>
      </main>

      <nav className="mobile-bottom-nav" aria-label="Nawigacja mobilna">
        {navigation.map((item) => {
          const Icon = item.icon;
          return <button key={item.id} className={view === item.id ? "active" : ""} onClick={() => changeView(item.id)}><Icon size={20} /><span>{item.label}</span></button>;
        })}
        <button className="mobile-add" onClick={() => setUploadOpen(true)}><Plus size={22} /><span>Dodaj</span></button>
      </nav>

      <UploadModal open={uploadOpen} onClose={() => setUploadOpen(false)} onUpload={uploadReceipt} />
      <ApiSettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} onSaved={() => void loadData()} />
      {toast && <div className="toast"><CheckCircle2 size={18} /> {toast}</div>}
    </div>
  );
}

function ApiSettingsModal({ open, onClose, onSaved }: { open: boolean; onClose: () => void; onSaved: () => void }) {
  const [token, setToken] = useState("");
  useEffect(() => { if (open) setToken(getStoredToken()); }, [open]);
  if (!open) return null;
  const submit = () => { saveToken(token); onClose(); onSaved(); };
  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <section className="settings-modal" onMouseDown={(event) => event.stopPropagation()}>
        <header className="modal-header"><div><span className="eyebrow">Połączenie</span><h2>Token dostępu</h2><p>Przy wyłączonym uwierzytelnianiu lokalnym zostaw to pole puste.</p></div><button className="icon-button" onClick={onClose}><X size={20} /></button></header>
        <label className="token-field"><span>Supabase access token</span><textarea value={token} onChange={(event) => setToken(event.target.value)} placeholder="eyJhbGciOi…" /></label>
        <footer className="modal-actions"><button className="button button-ghost" onClick={onClose}>Anuluj</button><button className="button button-primary" onClick={submit}>Zapisz i połącz</button></footer>
      </section>
    </div>
  );
}
