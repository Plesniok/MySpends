export type ReceiptStatus = "uploaded" | "processing" | "needs_review" | "completed" | "failed";

export interface ReceiptItem {
  id: string;
  product_id: string | null;
  category_id: string | null;
  position: number;
  raw_name: string;
  normalized_name: string | null;
  quantity: string;
  unit: string;
  unit_price_grosze: number | null;
  original_total_price_grosze: number | null;
  discount_grosze: number;
  total_price_grosze: number;
  confidence: string | null;
  bounding_box: Record<string, unknown> | null;
  created_at: string;
}

export interface ReceiptDeposit {
  id: string;
  position: number;
  raw_name: string;
  quantity: string;
  unit_amount_grosze: number;
  total_grosze: number;
  confidence: string | null;
  created_at: string;
}

export interface Receipt {
  id: string;
  merchant: string | null;
  purchased_at: string | null;
  total_grosze: number | null;
  subtotal_grosze: number | null;
  deposit_total_grosze: number;
  currency: string;
  image_path: string | null;
  status: ReceiptStatus;
  raw_ocr_text: string | null;
  extraction_json: Record<string, unknown> | null;
  processing_error: string | null;
  created_at: string;
  updated_at: string;
  items: ReceiptItem[];
  deposits: ReceiptDeposit[];
}

export interface Product {
  id: string;
  canonical_name: string;
  category_id: string | null;
  created_at: string;
}

export interface Category {
  id: string;
  owner_id: string | null;
  name: string;
  slug: string;
  created_at: string;
}

export interface SignedImageUrl {
  url: string;
  expires_in: number;
}
