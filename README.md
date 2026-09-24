# Coinoskobi DexBot

<!-- CANONICAL_CURRENT_STATE_20260924 -->
## Current operational baseline — 2026-09-24

Reference commit: `72c71a04632556c596493ba9fecb17a60e2ecbd2`.

Current production-facing PAPER operation is narrower than the full architecture:

- network: BSC
- current DEX focus: PancakeSwap
- active universe observation quote: USDT only
- active hot-path quote: USDT only
- PAPER entry admission: USDT pairs only
- non-USDT PAPER candidates fail closed with `NON_USDT_QUOTE`
- panel universe follows the same USDT-only operating policy

This is an **active runtime policy**, not a permanent architectural ban on other quote assets.

### Quick start / verification

Current deployed environment uses Python 3.13.

```text
cd /root/projects/coinoskobi-dexbot
./.venv/bin/python -m pytest -q
systemctl is-active coinoskobi-paper-runtime.service
systemctl is-active coinoskobi-panel.service
```

Runtime configuration is supplied from the project environment. Secrets must not be committed.

Some simulation paths may require external tooling such as Anvil. Tool presence never grants LIVE, wallet, signing or order-create authority.

Documentation ownership:
- `README.md`: stable contract + quick start
- `ROADMAP.md`: Phase 0–15 ownership/state
- `PROJECT_STATE.md`: current verified checkpoint + historical seals
- `planlı yapılacaklar.md`: active/next/backlog tracker


Coinoskobi, BNB Chain / PancakeSwap odaklı; fırsat keşfi, DEX piyasa gözlemi, risk değerlendirmesi, paper işlem yaşam döngüsü ve operatör karar desteği sağlayan modüler bir sistemdir.

Temel ilke:

**Doğrulanmış veri, güvenlik, bounded çalışma ve authority ayrımı işlem sıklığından önce gelir.**

## Canonical State

- Tek resmi mimari sınıflandırma: **PHASE 0–15**
- Phase 0–15: **CLOSED**
- Phase 15: **FINAL ROADMAP PHASE**
- Yeni Phase 16 / ERA / architecture V2/V3 / OCR / R-number / post-roadmap zinciri açılmaz.
- PancakeSwap V2/V3 adları yalnız gerçek DEX protokol sürümünü ifade eder.
- Sonraki bakım ve düzeltmeler mevcut Phase 0–15 sahipliğine atanır.
- Production odağı: **BNB Chain (BSC) + PancakeSwap**
- Universe büyüklüğü dinamiktir; sabit token/pool sayısı mimari kural olamaz.
- Live execution authority: **0**
- Wallet/signing authority: **0**
- AI trade authority: **0**

Canonical faz sahipliği ve mimari sınırlar için `ROADMAP.md`, güncel operasyonel checkpoint için `PROJECT_STATE.md`, tarihsel doğrulama kanıtları için `TEST_RESULTS.md` kullanılır.

## Canonical Maintenance Routing Protocol

Bu protokol yeni sohbet, yeni AI/agent oturumu ve tüm maintenance çalışmaları için zorunludur:

1. Önce `README.md` → `ROADMAP.md` → `PROJECT_STATE.md` → `TEST_RESULTS.md` okunur.
2. `PROJECT_STATE.md` aktif bir maintenance tracker işaret ediyorsa, planlama/uygulamadan önce o tracker da okunur. Güncel aktif tracker: `planlı yapılacaklar.md`.
3. Yeni iş önce mevcut **Phase 0–15** ana sahipliğine atanır.
4. İlgili ana Phase altındaki mevcut düz-harf alt fazlar (`A/B/C/D...`) kontrol edilir.
5. İş mevcut bir alt fazın kapsamındaysa yeni alt faz açılmaz; **mevcut alt faz güncellenir/değiştirilir**.
6. İş mevcut alt fazların hiçbirine gerçekten sığmayan ayrı ve kalıcı bir sahiplik gerektiriyorsa yalnız aynı ana Phase altında **sıradaki kullanılmamış düz harf** açılabilir.
7. İç içe numaralandırma (`14B1`, `12B2A` vb.), yeni Phase, ERA, architecture V2/V3 veya paralel roadmap oluşturulmaz.
8. Yeni modül/script/service/provider/router eklemeden önce repository-wide mevcut implementation aranır; mümkünse mevcut canonical parça genişletilir veya değiştirilir. Paralel/duplicate mimari kurulmaz.
9. Kullanılmayan, duplicate, superseded, debug/disposable veya artık referanslanmayan executable script/modül/config/test-helper dosyaları reference audit + test sonrasında kaldırılır. Tarihsel audit/evidence belgeleri kanıt olarak tutulabilir; dead executable code tutulmaz.
10. Mimari iskelet, canonical data flow, authority sınırları, runtime/DB sahipliği ve fail-closed güvenlik davranışı korunur; bakım işi mimari mutasyon gerekçesi değildir.
11. Kapanış sırası: targeted test → canonical smoke/E2E → gerekiyorsa full regression → post-audit → GitHub → VPS sync/runtime acceptance.

Alt faz açmak normal bug-fix mekanizması değildir. Küçük düzeltme/refactor/test/provider ayarı/panel düzeltmesi mevcut sahiplik içinde maintenance olarak kalır. Ayrıntılı ve bağlayıcı sınıflandırma kuralı `ROADMAP.md` içindeki **MİMARİ ANAYASA** ve **ALT FAZ YÖNETİM PROTOKOLÜ** bölümlerindedir.

## Canonical Runtime

- Main application: `main.py`
- Panel backend/application: `app/api/panel.py` / `app.api.panel:app`
- Panel frontend: `app/api/static/index.html`
- Panel port: `8098`
- Paper DB: `data/paper_trades.db`
- Cache/universe DB: `data/cache/cache.db`
- Paper service: `coinoskobi-paper-runtime.service`
- Panel service: `coinoskobi-panel.service`

Yan/test/V2/V3 panel veya paralel runtime oluşturulmaz.

## Canonical Data Flow

1. Provider broker / DEX sources
2. Discovery ve source adapters
3. Normalization / ingress
4. Bounded candidate admission
5. Analyzer / cache
6. Market intelligence
7. Risk ve feasibility
8. Deterministic decision support
9. Paper admission
10. Position lifecycle
11. Outcome / calibration evidence
12. Read-only Command Center

External data acquisition, observation, decision, paper, wallet, signing ve live execution authority ayrı sorumluluklardır.

## Provider Architecture

On-chain RPC/WSS erişiminin canonical giriş noktası **provider broker** katmanıdır.

Canonical dosya sınırları:

- `app/chains/bsc.py` — BSC Web3 composition/root binding
- `app/dex/provider_broker.py` — HTTP/WSS provider seçimi, bounded failover ve quota control
- `app/dex/provider_resilience.py` — saf failure classification / cooldown policy
- `app/dex/wss_service.py` — application-owned WSS lifecycle

Broker kuralları:

- en fazla dört explicit RPC/WSS provider slotu desteklenir
- aynı URL duplicate provider olarak eklenmez
- rate-limit/quota/403 ve transient transport hataları sınıflandırılır
- quota/rate-limit alan provider circuit-breaker ile cooldown süresince devreden çıkarılır
- tüm circuit'ler açıksa yeni gereksiz RPC üretmeden fail-fast edilir
- ağır RPC metodları sağlıklı provider'lar arasında bounded dağıtılabilir
- kısa ömürlü exact-request cache ve in-flight coalescing tekrar çağrıları azaltır
- WSS fallback bounded ve primary-first çalışır
- provider URL/secret değerleri status/log çıktısına verilmez
- provider broker decision, paper, wallet, signing veya execution authority taşımaz

Provider sayısını artırmak, sınırsız trafik izni değildir. Hot path pahalı RPC/history scan beklemez; ağır provider işi bounded slow-path/worker katmanında kalır.

Diğer external provider rolleri:

- GeckoTerminal: discovery ve bounded indexed market data
- DexScreener: bounded universe market snapshot ve okunabilir base/quote metadata
- GoPlus / Honeypot.is: sellability/security evidence

Provider hatası veya eksik veri `SAFE` anlamına gelmez. Eksik evidence `UNKNOWN` olarak korunur.

## Phase Ownership Summary

- **Phase 0:** erken kritik bug fix ve temel cleanup
- **Phase 1:** core infrastructure, SQLite/schema/concurrency/recovery
- **Phase 2:** bounded pipeline, candidate queue, durable UniverseRegistry ve discovery
- **Phase 3:** risk, sellability, cost ve entry feasibility
- **Phase 4:** deterministic position lifecycle
- **Phase 5:** DEX market intelligence ve bounded market snapshots
- **Phase 6:** exit intelligence
- **Phase 7:** flow confirmation, regime ve COLD/WARM/HOT seismic state
- **Phase 8:** native WSS ingestion ve canonical provider resilience/broker
- **Phase 9:** wallet/entity/smart-money intelligence
- **Phase 10:** adversary/scam/MEV intelligence
- **Phase 11:** learning/calibration/outcome memory; proposal-only
- **Phase 12:** operational paper runtime, restart/recovery, provider operability ve E2E composition
- **Phase 13:** paper/counterfactual outcome calibration, data-integrity ve bounded observation pressure
- **Phase 14:** canonical Command Center, panel ve readable token/pool display
- **Phase 15:** final operational validation ve yalnız explicit approval ile micro-live boundary

Ayrıntılı sahiplik `ROADMAP.md` içindedir.

## Universe and Market State

Universe provider-neutral ve durable registry üzerinden tutulur. Pool yaşlandığı veya geçici olarak düşük aktivite gösterdiği için registry'den silinmez.

COLD / WARM / HOT yalnız **market seismic state** anlamındadır:

- COLD: geniş ve daha düşük maliyetli gözlem
- WARM: anlamlı hareket gösteren subset
- HOT: anomalous / hızlı hareket eden ve daha sık native gözleme aday subset

Bu isimler analyzer-cache durumlarıyla karıştırılmaz.

## Token and Pool Display Metadata

Canonical identity ile kullanıcıya gösterilen isim ayrıdır.

- Pool identity: chain + dex + pool
- Token identity: chain-aware address
- DexScreener snapshotlarındaki base/quote symbol ve name bilgisi yalnız display metadata olarak saklanabilir.
- Display metadata hiçbir zaman identity, decision veya execution authority değiştirmez.
- Panel yalnız bounded readmodel üzerinden okunabilir isim gösterir.

## Risk and Safety

- Hard safety, matematiksel score'dan üstündür.
- Confirmed danger veto üretebilir.
- Suspicion proof değildir.
- UNKNOWN otomatik danger veya otomatik safe değildir.
- Sellability, liquidity, execution-cost ve exit-capacity evidence korunur.
- Private key, seed phrase ve provider secret repository'ye yazılmaz.
- Live/wallet/signing yetkisi default olarak kapalıdır.

## Paper and Learning Boundary

Paper runtime gerçek para kullanmaz. Paper OPEN/CLOSE, restart/recovery ve outcome replay deterministic kontratlar altında yürütülür.

Learning/calibration katmanı:

- geçmiş outcome evidence toplar
- false-positive / false-negative ve missed-opportunity bağlamı üretir
- proposal oluşturabilir
- threshold/config/source-code değişikliğini otomatik apply edemez
- trade permission veya execution authority kazanamaz

Counterfactual provider trafiği bounded kalır. Bir scanner refresh içinde pending counterfactual Gecko fetch'i 30 pool ile sınırlandırılır; kalanlar sonraki normal refresh'e bırakılır.

## Command Center

Tek canonical panel **İŞLEM MERKEZİ**'dir.

Panel:

- gerçek backend/DB evidence gösterir
- fake token/fiyat/P&L/wallet/sistem verisi kullanmaz
- bounded candidate/universe radar sunar
- paper ledger/accounting/health/intelligence readmodels gösterir
- AI kullanıldığında açıklama/özet/proposal sınırında kalır
- strategy, paper, wallet, signing veya live execution authority taşımaz

UI değişiklikleri Phase 14 sahipliğinde targeted olarak yapılır; unrelated full-page replacement yapılmaz.

## Development and Validation

Kalıcı değişiklik sırası:

1. Mevcut Phase 0–15 sahipliğini belirle
2. Targeted implementation
3. Targeted tests
4. Canonical smoke/E2E
5. Gerekiyorsa full regression
6. Compile / DB integrity / post-audit
7. GitHub merge
8. VPS clean-state doğrulaması
9. Fast-forward synchronization
10. Runtime acceptance

Provider/resilience değişikliklerinde canonical smoke kapısı `tests/test_provider_broker.py` kapsamını da içerir.

Bir PASS tamamlanmadan sonraki riskli adıma geçilmez.

## Repository Rules

- gereksiz duplicate modül yok
- disposable script kalıcı mimari değildir
- provider erişimi için paralel failover katmanları oluşturulmaz
- hot path pahalı RPC/history scan/AI beklemez
- ağır işler bounded worker/slow-path üzerinde çalışır
- queue/cache/readmodel yapıları bounded kalır
- network/DEX için pipeline kopyalanmaz
- tarihsel commit/test adları yeni roadmap zinciri sayılmaz
- maintenance işi yeni Phase açmak yerine mevcut Phase 0–15'e bağlanır
- mevcut alt faz sahipliği varken aynı kapsam için yeni alt faz açılmaz
- yeni executable dosya eklemeden önce existing implementation/reference audit yapılır
- unused/duplicate/superseded executable script/modül/config/test-helper reference audit + test sonrası kaldırılır

## Repository Structure

Ana alanlar:

- `app/analyzer/`
- `app/api/`
- `app/cache/`
- `app/chains/`
- `app/config/`
- `app/dex/`
- `app/filter/`
- `app/learning/`
- `app/paper/`
- `app/pipeline/`
- `app/risk/`
- `app/scanner/`
- `app/strategy/`
- `app/universe/`
- `tests/`

## Canonical Documents

Repository'de aktif canonical dokümantasyon:

- `README.md` — proje özeti ve kalıcı çalışma kuralları
- `ROADMAP.md` — tek Phase 0–15 mimari/sahiplik haritası
- `PROJECT_STATE.md` — operasyonel continuation checkpoint
- `TEST_RESULTS.md` — tarihsel doğrulama kanıtları

Phase-scoped tarihsel raporlar audit evidence olarak kalabilir; aktif paralel roadmap değildir.

## Security

Repository'ye asla commit edilmez:

- private key
- seed phrase
- wallet secret
- exchange API secret
- provider secret

## Core Stack

Python 3, SQLite, Web3.py, FastAPI, BNB Chain, PancakeSwap, GeckoTerminal, DexScreener ve pytest.
