import type { Category, Product, Receipt, SignedImageUrl } from "./types";

const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8029/api/v1").replace(/\/$/, "");
const TOKEN_KEY = "my-spends-access-token";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function getStoredToken(): string {
  return localStorage.getItem(TOKEN_KEY) || import.meta.env.VITE_SUPABASE_ACCESS_TOKEN || "";
}

export function saveToken(token: string): void {
  const value = token.trim();
  if (value) localStorage.setItem(TOKEN_KEY, value);
  else localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getStoredToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");

  const response = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (!response.ok) {
    let message = `Błąd API (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: string | Array<{ msg?: string }> };
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail)) message = body.detail.map((item) => item.msg).join(", ");
    } catch {
      // The status is still useful when the backend did not return JSON.
    }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  receipts: () => request<Receipt[]>("/receipts?limit=200"),
  receipt: (id: string) => request<Receipt>(`/receipts/${id}`),
  categories: () => request<Category[]>("/categories"),
  products: () => request<Product[]>("/products?limit=200"),
  imageUrl: (id: string) => request<SignedImageUrl>(`/receipts/${id}/image-url`),
  uploadReceipt: (file: File) => {
    const data = new FormData();
    data.append("file", file);
    return request<Receipt>("/receipts/upload", { method: "POST", body: data });
  },
  updateProductCategory: (productId: string, categoryId: string | null) =>
    request<Product>(`/products/${productId}/category`, {
      method: "PATCH",
      body: JSON.stringify({ category_id: categoryId }),
    }),
};
