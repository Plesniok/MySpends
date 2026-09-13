# My Spends API

Backend FastAPI do automatycznego odczytywania paragonów. Dane relacyjne trafiają do
Supabase PostgreSQL, zdjęcia do prywatnego Supabase Storage, a lokalny model vision przez
Ollama rozpoznaje sklep, datę, sumę oraz wszystkie pozycje.

Pierwsza wersja zawiera:

- upload samego zdjęcia paragonu (JPEG, PNG, WebP, HEIC, HEIF),
- lokalne rozpoznawanie paragonu przez Qwen3-VL i Ollama,
- prywatne, krótkotrwałe linki do zdjęć,
- automatyczne pozycje z ilością, jednostką i cenami,
- automatyczne produkty kanoniczne oraz aliasy sklepowe nazw,
- automatyczne przypisanie istniejącej kategorii i możliwość jej poprawienia,
- izolację danych według identyfikatora użytkownika,
- kwoty zapisywane jako liczba groszy,
- migracje Alembic i startowy zestaw kategorii,
- pełny wynik ekstrakcji, transkrypcję OCR i confidence.

## 1. Projekt Supabase

Utwórz darmowy projekt Supabase. W Dashboardzie otwórz **Connect** i skopiuj connection
string. Dla stale działającego FastAPI na sieci IPv4 wybierz **Session pooler, port 5432**.

Potrzebne wartości:

- Project URL,
- secret key (`sb_secret_...`) dla backendu,
- publishable key (`sb_publishable_...`) dopiero dla przyszłego frontendu,
- hasło do bazy i connection string.

W nowych projektach Supabase klucze nazywają się `Publishable key` i `Secret key`. Starsze nazwy
`anon` i `service_role` są legacy; backend nadal je akceptuje jako fallback. Klucz secret daje
pełny dostęp, omija RLS i może znajdować się wyłącznie w zmiennych środowiskowych backendu.
Nie dodawaj go do frontendu ani repozytorium.

Klucze znajdziesz w **Settings -> API Keys -> Publishable and secret API keys**. Jeżeli sekcja
nie zawiera jeszcze klucza secret, wybierz **Create new API keys**.

## 2. Instalacja

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
```

Uzupełnij `.env`. Hasło w `DATABASE_URL` musi być zakodowane jak składnik URL, jeśli zawiera
znaki specjalne, np. `@`, `/` lub `#`.

### Lokalny model AI

Zainstaluj Ollama w wersji 0.12.7 lub nowszej, uruchom usługę i pobierz domyślny model:

```bash
ollama pull qwen3-vl:4b-instruct
```

Model zajmuje około 3,3 GB. Pierwsza analiza może potrwać dłużej z powodu załadowania modelu
do pamięci. Konfiguracja backendu:

```dotenv
RECEIPT_AI_ENABLED=true
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3-vl:4b-instruct
OLLAMA_CONTEXT_LENGTH=8192
OLLAMA_TIMEOUT_SECONDS=300
RECEIPT_IMAGE_MAX_DIMENSION=2560
RECEIPT_IMAGE_WEBP_QUALITY=82
RECEIPT_IMAGE_MAX_PIXELS=50000000
RECEIPT_AUTO_COMPLETE_CONFIDENCE=0.70
```

Używaj wariantu `-instruct`. Tag `qwen3-vl:4b` wskazuje model thinking, który przy ekstrakcji
strukturalnego JSON może zużyć generowanie na tok rozumowania i zwrócić pustą odpowiedź.

Możesz sprawdzić Ollama poleceniem `curl http://127.0.0.1:11434/api/version`. Jeśli backend
działa w kontenerze, `127.0.0.1` wskazuje kontener, więc ustaw adres hosta z Ollama.

## 3. Migracja i bucket

```bash
alembic upgrade head
python -m app.scripts.bootstrap_storage
```

Migracja tworzy tabele oraz włącza na nich RLS bez publicznych polityk. Dzięki temu tabele nie
są dostępne z anon key przez Data API. FastAPI łączy się prywatnym connection stringiem i przy
każdym zapytaniu filtruje dane po `owner_id`.

Skrypt storage tworzy prywatny bucket `receipts` z limitem 10 MB i dozwolonymi typami obrazów.
Backend używa klucza service role do operacji na plikach, ale wcześniej sprawdza właściciela
paragonu w bazie.

## 4. Uruchomienie

```bash
uvicorn app.main:app --reload
```

- Swagger UI: <http://localhost:8000/docs>
- Healthcheck: <http://localhost:8000/api/v1/health>
- Kontrola bazy: <http://localhost:8000/api/v1/health/database>

Do chronionych endpointów wysyłaj access token otrzymany po logowaniu przez Supabase Auth:

```http
Authorization: Bearer SUPABASE_ACCESS_TOKEN
```

Do lokalnego testowania bez frontendu można tymczasowo ustawić:

```dotenv
AUTH_DISABLED=true
DEV_USER_ID=00000000-0000-0000-0000-000000000001
```

Nie używaj `AUTH_DISABLED=true` na publicznym serwerze.

### Frontend

Responsywny frontend React znajduje się w katalogu `frontend`. Obsługuje upload zdjęcia,
dashboard wydatków, listę paragonów, podgląd prywatnego pliku, produkty oraz zmianę kategorii.

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Aplikacja jest dostępna pod <http://localhost:5173>. Domyślnie łączy się z API pod
`http://localhost:8000/api/v1`. Przy włączonym Supabase Auth token można wkleić w ustawieniach
frontendu albo podać jako `VITE_SUPABASE_ACCESS_TOKEN`.

### Docker Compose

Do uruchomienia obu aplikacji użyj jednego polecenia z katalogu projektu:

```bash
docker compose up --build
```

Po starcie frontend jest dostępny pod <http://localhost:8080>, a Swagger API pod
<http://localhost:8000/docs>. Frontend korzysta z `/api/v1` przez wewnętrzny reverse proxy Nginx,
więc nie wymaga osobnej konfiguracji CORS.

Compose automatycznie wykonuje migracje oraz tworzy prywatny bucket. Ollama pozostaje procesem na
hoście. Na Linuksie Compose uruchamia mały, prywatny most pomiędzy interfejsem Docker a
`127.0.0.1:11434`, więc Ollama nie musi być wystawiona na sieć Wi-Fi. Kontener API łączy się z
nim pod `host.docker.internal:11434`. Jeśli Docker używa innego adresu niż `172.17.0.1`, ustaw
`OLLAMA_BRIDGE_ADDRESS` w `.env` na adres pokazany przez `ip -4 addr show docker0`.

## Automatyczny upload

Jedynym wymaganym polem jest `file`. Nie trzeba wcześniej tworzyć produktu, aliasu ani pozycji
paragonu:

```bash
curl -X POST http://localhost:8000/api/v1/receipts/upload \
  -H "Authorization: Bearer SUPABASE_ACCESS_TOKEN" \
  -F "file=@paragon.jpg"
```

Backend zapisuje zdjęcie i paragon ze statusem `processing`, po czym od razu zwraca
`202 Accepted`. Analiza przez lokalny model działa w tle i tworzy pozycje, produkty oraz aliasy.
Aktualny wynik można pobierać przez `GET /api/v1/receipts/{id}`. Frontend robi to automatycznie
co 3 sekundy, aż status zmieni się na `completed`, `needs_review` albo `failed`.

Przed wysłaniem do Supabase Storage backend obraca zdjęcie zgodnie z EXIF, ogranicza dłuższy
bok domyślnie do 2560 px i zapisuje je jako WebP z jakością 82. Do Storage i modelu trafia już
wersja skompresowana bez metadanych EXIF; limity można zmienić przez zmienne
`RECEIPT_IMAGE_MAX_DIMENSION` i `RECEIPT_IMAGE_WEBP_QUALITY`.

Model tworzy paragon, pozycje,
produkty kanoniczne i aliasy nazw. Przykładowo `MLEKO ŁACIATE BUT. 1` pozostaje nazwą surową,
a jego produkt kanoniczny może otrzymać nazwę `mleko`. Gdy inny paragon zawiera kolejny wariant
tej nazwy, alias wskazuje ten sam produkt.

Rabaty umieszczone bezpośrednio pod produktem (`RABAT`, `OPUST`, wartość ujemna) są przypisywane
do poprzedniej pozycji. Pozycja przechowuje cenę przed rabatem, wartość rabatu i cenę końcową;
sumy kategorii, produktów oraz paragonu używają ceny końcowej.

Kaucje za puszki i butelki są przechowywane oddzielnie od produktów. `subtotal_grosze` oznacza
wartość produktów z wiersza `SUMA PLN`, `deposit_total_grosze` sumę kaucji, a `total_grosze`
faktyczną kwotę `DO ZAPŁATY`. Każdy wiersz kaucji zachowuje liczbę opakowań, stawkę jednostkową
i łączną wartość, np. `2 × 0,50 zł = 1,00 zł`.

Model wybiera kategorię wyłącznie spośród kategorii dostępnych w bazie. Kategorię produktu
można później zmienić; zmiana aktualizuje również zapisane pozycje tego produktu. Status
`completed` oznacza, że suma pozycji zgadza się z sumą paragonu i confidence przekracza próg.
W przeciwnym razie dane nadal są zapisywane ze statusem `needs_review`.

## Najważniejsze endpointy

| Metoda | Endpoint | Znaczenie |
|---|---|---|
| `GET` | `/api/v1/categories` | Kategorie globalne i własne |
| `GET` | `/api/v1/products` | Produkty automatycznie utworzone przez AI |
| `PATCH` | `/api/v1/products/{id}/category` | Zmiana kategorii produktu i jego pozycji |
| `POST` | `/api/v1/receipts/upload` | Upload zdjęcia, zlecenie analizy w tle (`202`) |
| `GET` | `/api/v1/receipts/{id}/image-url` | Podpisany link do prywatnego zdjęcia |
| `GET` | `/api/v1/receipts/{id}` | Paragon wraz z automatycznymi pozycjami |

Przykład zmiany kategorii produktu:

```json
{
  "category_id": "10000000-0000-0000-0000-000000000001"
}
```

## Testy

```bash
pytest
ruff check .
```

Testy używają SQLite w pamięci i nie łączą się z prawdziwym projektem Supabase.
