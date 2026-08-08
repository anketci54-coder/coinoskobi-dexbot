# COINOSKOBI DEXBOT — ROADMAP

> Bu dosya projenin resmi geliştirme planıdır.
> Her faz tamamlandığında yalnızca ilgili maddeler işaretlenir.
> Faz dışı geliştirme yapılmaz.

---

# ÇALIŞMA AKIŞI

1. Problem Statement
2. Kod
3. Compile
4. Import
5. Test
6. Smoke Test
7. Commit
8. Push
9. Roadmap Güncelle
10. Final Audit

Hiçbir faz bu 10 adım tamamlanmadan kapanmaz.

---

# KURALLAR

- Geçici script yok.
- Yama yok.
- Duplicate kod yok.
- Kullanılmayan dosya yok.
- Kullanılmayan import yok.
- Bir commit = Bir amaç.
- Bir PR = Bir faz.

---

# PROJE DURUMU

Current Phase : PHASE 1

Progress

- Phase 0 : ⏳
- Phase 1 : 🚧
- Phase 2 : ⏳
- Phase 3 : ⏳
- Phase 4 : ⏳
- Phase 5 : ⏳
- Phase 6 : ⏳

---

# PHASE 0 — Critical Bug Fixes

Amaç

Botun gerçekten çalışır hale gelmesi.

## Yapılacaklar

- [x] gecko_pool_cache → price_usd desteği
- [x] CachePrice uyumluluğu
- [x] ALLOWED_DEX filtresi
- [ ] requirements.txt temizliği
- [ ] app/scanner/pairs.py sil
- [ ] duplicate portfolio kaldır

Status

🚧 In Progress

---

# PHASE 1 — Core Infrastructure

Amaç

Temiz ve sürdürülebilir altyapı.

## Yapılacaklar

- [x] app/core/logger.py
- [x] app/core/runner.py
- [ ] app/paper/database.py
    - WAL mode
    - singleton
- [x] app/config/trading.py
- [ ] app/config/contracts.py
- [ ] main.py sadeleştirme
- [ ] factory.py kaldır
- [ ] routers.py kaldır
- [ ] tokens.py kaldır

Status

🚧 In Progress

---

# PHASE 2 — Performance

Amaç

Pipeline hızlandırılması.

## Yapılacaklar

- [ ] analyzer/token async
- [ ] analyzer/pair async
- [ ] risk/bytecode async
- [ ] Runner parallel RPC
- [ ] PortfolioService
- [ ] Manager refactor
- [ ] API refactor
- [ ] aiohttp

Status

⏳ Waiting

---

# PHASE 3 — Strategy

Amaç

Karar kalitesini artırmak.

## Yapılacaklar

- [ ] Honeypot
- [ ] Strategy config
- [ ] Config driven thresholds
- [ ] Pool age filter
- [ ] Exposure limits

Status

⏳ Waiting

---

# PHASE 4 — API

Amaç

Deployment.

## Yapılacaklar

- [ ] FastAPI auth
- [ ] Health endpoint
- [ ] Stats endpoint
- [ ] Dockerfile
- [ ] docker-compose
- [ ] .env.example

Status

⏳ Waiting

---

# PHASE 5 — Metrics

Amaç

Gözlemlenebilirlik.

## Yapılacaklar

- [ ] Metrics
- [ ] Telegram Alerts
- [ ] /metrics
- [ ] Telegram env

Status

⏳ Waiting

---

# PHASE 6 — Live Preparation

Amaç

Paper Trading doğrulandıktan sonra Live Trading hazırlığı.

## Yapılacaklar

- [ ] Swap Engine
- [ ] Execution Guard
- [ ] Trading Mode
- [ ] Private RPC
- [ ] Emergency Stop

Status

⏳ Waiting

---

# Definition of Done

Bir görev ancak aşağıdakilerin tamamı PASS ise tamamlanmış sayılır.

- Plan
- Code
- Compile
- Import
- Test
- Smoke Test
- Commit
- Push
- Roadmap Update
- Final Audit

---

# Test History

Phase 1

- Compile ✅
- Import ✅
- 55/55 Tests ✅
- Smoke Test ✅
- Pipeline PASS ✅
- Git Clean ✅
