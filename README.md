## AI Stock Price Prediction Platform (Docker)

### Prereqs

- Docker Desktop
- Finnhub API key

### Quick start

1. Create a `.env` file in the project root:

```bash
cp .env.example .env
```

2. Edit `.env` and set:

```text
FINNHUB_API_KEY=your_key_here
ALPHAVANTAGE_API_KEY=your_key_here
```

3. Start everything:

```bash
docker compose up --build
```

Or with Make:

```bash
make up
```

### Faster startup after first build

After the first successful build, you can start without rebuilding:

```bash
make up-fast
```

Run in background (detached):

```bash
make up-d
```

### URLs

- **Single website (gateway)**: `http://127.0.0.1`
- **Backend docs (via gateway)**: `http://127.0.0.1/api/docs`
- **INR FX endpoint (via gateway)**: `http://127.0.0.1/api/v1/stocks/fx/inr?base=USD`

### Stop

```bash
docker compose down
```

Or:

```bash
make down
```
