# COINOSKOBI — PLANLI YAPILACAKLAR

<!-- CANONICAL_CURRENT_STATE_20260924 -->
## AKTİF ÇALIŞMA DÜZENİ — 2026-09-24

Referans commit:

`72c71a04632556c596493ba9fecb17a60e2ecbd2`

Bu dosya aktif çalışma takipçisidir; README/ROADMAP içindeki canonical kuralların ikinci kopyası değildir.

### ACTIVE NOW

1. Canonical dokümantasyon senkronizasyonu
   - çıktı: README, ROADMAP, PROJECT_STATE ve tracker arasında tutarlı durum
   - kabul: güncel runtime kapsamı yanlış temsil edilmeyecek
   - doğrulama: eski belge + yeni belge + mevcut kod bağımsız karşılaştırılacak

2. Phase 15H belge/sözleşme tutarlılığı
   - provider/broker/Anvil sınırı executable evidence ile karşılaştırılacak
   - kanıt yetersizse belirsizlik açık bırakılacak

### NEXT

- gerçek PAPER entry/exit/data incidentlerini ölçülebilir kök nedenle kapat
- kârlı hareketlerin neden kaçırıldığı ile zarar eden girişlerin neden kabul edildiğini runtime verisiyle karşılaştır
- mevcut çalışan çekirdeği koru

### CURRENT RUNTIME POLICY

- BSC
- PancakeSwap focus
- observation: USDT-only
- hot path: USDT-only
- panel universe: USDT-only
- PAPER entry: USDT-only
- non-USDT candidate: `SKIP / NON_USDT_QUOTE`

### BACKLOG / CONDITIONAL RESEARCH

Agent frameworkleri, model altyapıları, Aider/LiteLLM/RAG/QLoRA/distillation ve benzeri maddeler listede kalabilir ancak aktif iş sayılmaz. Somut ihtiyaç ve kabul kriteri oluşmadan kurulum/entegrasyon kararı değildir.

### WORK ITEM CONTRACT

Aktif iş mümkün olduğunda şunları taşımalıdır:
- mevcut durum
- teslim edilecek çıktı
- bağımlılık
- kabul kriteri
- doğrulama yöntemi

### VEZİR DEĞİŞİKLİK SINIRI

Aşağıdaki akış **hedeflenen kontrollü mühendislik politikasıdır; mevcut Vezir capability kanıtı değildir**:

`PROPOSE -> TEST -> DIFF -> SECOND REVIEW (gerektiğinde) -> HUMAN APPROVAL -> APPLY`

Sandbox/worktree değişikliği, production workspace değişikliği, commit, push ve deploy/restart ayrı yetki kapılarıdır. Bir aşamadaki onay, canonical politika açıkça belirtmedikçe sonraki aşamaların tümünü otomatik yetkilendirmez.

Aşağıdaki eski tracker içeriği tarihsel plan, kapanmış iş veya backlog bilgisi içerebilir. Üstteki ACTIVE/NEXT sınıflandırmasıyla çelişen eski madde otomatik olarak aktif iş sayılmaz.


Updated: 2026-09-20
Status: **ACTIVE**
Purpose: Coinoskobi Phase 0–15 mimarisini bozmadan devam eden bakım, geliştirme, Vezir, AI mühendislik, güvenlik, otomasyon ve optimizasyon çalışmalarının tek aktif takip belgesi.

> Bu dosya yeni bir ROADMAP değildir.
> Yeni Phase, ERA, V2/V3 veya paralel mimari oluşturmaz.
> `ROADMAP.md` tek canonical mimari haritasıdır.
> Bu dosya yalnız mevcut Phase 0–15 içinde devam eden işleri, tamamlananları ve sıradaki adımı takip eder.

---

# 1. ZORUNLU BOOT / DEVAM SIRASI

Yeni ChatGPT, Codex veya başka bir AI/agent oturumu Coinoskobi üzerinde çalışmadan önce şu sırayı uygular:

1. `README.md`
2. `ROADMAP.md`
3. `PROJECT_STATE.md`
4. `TEST_RESULTS.md`
5. `planlı yapılacaklar.md`

Ardından gerçek çalışma durumu ayrıca doğrulanır:

- repository HEAD
- local/VPS working tree
- `origin/main`
- aktif branch
- ilgili systemd servisleri
- paper/cache DB durumu
- açık PAPER pozisyonları
- varsa uncommitted değişiklikler

AI hafızası veya eski sohbet özeti repository/runtime truth’un önüne geçemez.

---

# 2. MİMARİ DEĞİŞMEZLER

- [x] Tek mimari: **Phase 0–15**
- [x] Phase 15 final roadmap phase
- [x] Phase 16 yok
- [x] ERA yok
- [x] architecture V2/V3 yok
- [x] paralel roadmap yok
- [x] ikinci Coinoskobi runtime yok
- [x] ikinci canonical panel yok
- [x] network/DEX başına pipeline kopyası yok
- [x] nested alt-faz numarası yok (`14B1`, `12B2A` vb.)
- [x] hard safety model/skor/tavsiyenin üstünde
- [x] missing/UNKNOWN evidence SAFE kabul edilmez
- [x] AI trade authority = 0
- [x] wallet/signing authority = 0
- [x] live execution authority = 0; Phase 15 explicit approval sınırı dışında açılamaz
- [x] private key / seed / secret repo-log-prompt içine yazılmaz

---

# 3. ALT FAZ YÖNETİM KURALI

Her yeni iş:

1. Önce mevcut Phase 0–15 ana sahibine atanır.
2. O Phase’in mevcut `A/B/C/D...` alt fazları kontrol edilir.
3. İş mevcut alt faz kapsamındaysa **o alt faz güncellenir**.
4. Mevcut alt fazların hiçbirine sığmayan ayrı ve kalıcı bir sahiplik gerekiyorsa yalnız aynı ana Phase altında **sıradaki boş harf** açılabilir.
5. Küçük bug fix, refactor, test, provider ayarı, panel düzeltmesi veya runtime repair için yeni alt faz açılmaz.
6. Yeni kod/modül/script/service/router eklenmeden önce mevcut implementation aranır.
7. Aynı işi yapan ikinci canonical yol kurulmaz.
8. Eski/duplicate/superseded/dead executable kod reference audit + test sonrası silinir.
9. Tarihsel audit/closure MD dosyaları kanıt olarak tutulabilir.

---

# 4. HISTORICAL / BACKLOG ANA HEDEFLER

> Bu bölüm eski ayrıntılı çalışma hedeflerini korur. Güncel aktif çalışma hattı değildir; güncel yürütme sırası dosyanın en üstündeki **ACTIVE NOW / NEXT** bölümüdür.

Tarihsel plan dört büyük amacı birlikte ele alıyordu:

### A. PAPER runtime’ı güvenilir şekilde kapatmak
Mevcut PAPER recovery, sizing, manager, price refresh, exit ve accounting zinciri temiz biçimde doğrulanacak.

### B. AI mühendislik maliyetini ve token tüketimini ciddi azaltmak
Local evidence + düşük maliyetli modeller + güçlü model escalation sistemi kurulacak.

### C. Vezir’i gerçek Coinoskobi operasyon ajanına dönüştürmek
Vezir yalnız hazır sorulara cevap veren intent router olmaktan çıkacak.

### D. Sistemi sadeleştirmek
Eski scriptler, duplicate yollar, gereksiz deney kodları ve superseded parçalar sistemde bırakılmayacak.

---

# 5. PAPER RUNTIME RECOVERY CLOSURE

**Owner:** mevcut Phase 3 / Phase 4 / Phase 12 sahiplikleri.
**Status:** CLOSED / VERIFIED — 2026-09-20.

- [x] VPS current HEAD doğrulandı
- [x] working tree doğrulandı
- [x] uncommitted değişiklikler kapatıldı
- [x] `.bak`, debug ve disposable dosya kontrolü yapıldı
- [x] `AUTO/MANUAL` control state doğrulandı
- [x] manager `NoneType` recovery kapatıldı
- [x] açık PAPER pozisyon refresh zinciri doğrulandı
- [x] exit manager fresh-price evidence zinciri doğrulandı
- [x] devasa sizing korumaları doğrulandı
- [x] bootstrap/degraded sizing bounded hale getirildi
- [x] PnL/accounting invariants doğrulandı
- [x] SQLite integrity doğrulandı
- [x] targeted tests tamamlandı
- [x] paper/exit/panel regression tamamlandı
- [x] `git diff --check` PASS
- [x] runtime smoke tamamlandı
- [x] final diff review tamamlandı
- [x] commit/push tamamlandı
- [x] PROJECT_STATE recovery seal mevcut
- [x] TEST_RESULTS recovery evidence mevcut
- [x] HOT universe bridge SQLite thread-affinity regression kapatıldı
- [x] restart sonrası pair-price-history hydration kapatıldı
- [x] LP withdrawal protection doğrulanmamış adayların gerçek NORMAL/VUR_KAC PAPER sermayesi alması engellendi
- [x] follow-up snapshot source/liquidity/volume/buy/sell persistence alan eşlemesi düzeltildi

**Kural:** Yeni gerçek PAPER işlemlerinde görülen kritik entry/exit/data incidentleri eski recovery işini yeniden açmaz.
Her incident kendi owner Phase’inde **root cause → smallest fix → targeted test → deploy → tek runtime acceptance → close** sırasıyla çözülür.

---

# 6. REPOSITORY / SUBPHASE / DEAD-CODE ENVANTERİ

Yeni AI/Vezir implementation başlamadan önce yapılacak.

- [ ] Phase 8 subphase history
- [ ] Phase 11 subphase history
- [ ] Phase 12 subphase history
- [ ] Phase 13 subphase history
- [ ] Phase 14 subphase history
- [ ] mevcut AI/provider/router kodu
- [ ] Vezir backend
- [ ] Vezir frontend
- [ ] Vezir tests
- [ ] AI configs
- [ ] development-agent configs/scripts
- [ ] report/readmodel altyapısı
- [ ] duplicate provider/router
- [ ] stale experiment
- [ ] debug helper
- [ ] `.bak`
- [ ] kullanılmayan scriptler

Her parça:

`KEEP / MODIFY / REPLACE / REMOVE`

olarak sınıflandırılacak.

Bu envanter çıkmadan yeni `14X` veya başka alt-faz harfi verilmeyecek.

---

# 7. LOCAL EVIDENCE ENGINE / TOKEN AZALTMA

Ana prensip:

```text
BÜYÜK HAM VERİ
      ↓
LOCAL DETERMINISTIC TOOLS
      ↓
KÜÇÜK EVIDENCE PACKAGE
      ↓
LLM
```

LLM’ye bütün repo/log/DB gönderilmeyecek.

Önce kullanılacak:

```text
git
rg
SQLite
journalctl
pytest
repo symbol map
diff
local cache
local summaries
```

Örneğin:

```text
50.000 log
   ↓
local parser
   ↓
3 exception fingerprint
8 ilgili satır
2 ilgili fonksiyon
   ↓
AI
```

Görevler:

- [ ] repo-map
- [ ] symbol/function map
- [ ] Phase ownership map
- [ ] exception fingerprinting
- [ ] log dedup
- [ ] SQLite bounded aggregate
- [ ] bounded journal collection
- [ ] diff-only review context
- [ ] evidence freshness
- [ ] provenance
- [ ] context/token budget
- [ ] duplicate prompt suppression
- [ ] bounded cache

Bu yaklaşım token maliyetinin ana kontrol mekanizması olacak.

---

# 8. MULTI-MODEL AI MÜHENDİSLİK SİSTEMİ

Amaç:

**tek modele bağımlı olmamak.**

Temel çalışma sırası:

```text
0 — LLM YOK
git / rg / SQLite / pytest / journal / repo-map

        ↓

1 — FREE / CHEAP
triage
dosya seçimi
log classification
test summary

        ↓

2 — MID MODEL
küçük patch
ordinary root cause
unit test

        ↓

3 — STRONG MODEL
multi-file bug
security
architecture-sensitive issue

        ↓

4 — PREMIUM
yalnız çözülemeyen kritik problem

        ↓

5 — VERIFIER
yalnız task + diff + tests + evidence
```

Astra veya benzeri güçlü model her işin varsayılanı olmayacak.

---

# 9. CODEX + NVIDIA NIM

Backlog / conditional deney. Güncel ACTIVE/NEXT tamamlanmadan otomatik öncelik değildir.

Mevcut Codex CLI korunacak.

Amaç:

```text
Codex CLI
   │
   ├── OpenAI backend
   │
   └── NVIDIA NIM backend
```

Mevcut Codex config bozulmayacak.

İlk deney:

- [ ] NVIDIA ayrı profil
- [ ] READ ONLY
- [ ] repo inspection
- [ ] file/function finding
- [ ] test reasoning
- [ ] küçük benchmark
- [ ] sonra kontrollü edit/test

İlk benchmark adayları:

- Laguna XS 2.1
- DeepSeek/NVIDIA-hosted coding modelleri
- Nemotron ailesi

Model isimleri ve endpoint durumları implementasyon günü yeniden doğrulanacak; tracker’daki isimler adaydır.

---

# 10. AIDER

Aider özellikle:

- repo-map
- düşük context
- history summarization
- prompt caching

nedeniyle benchmark edilecek.

Ama:

**Coinoskobi runtime dependency olmayacak.**

Development tool olarak değerlendirilecek.

Test:

```text
aynı Coinoskobi görevi
Codex vs NVIDIA/Codex vs Aider
```

Ölç:

- doğru dosya
- root cause
- patch
- test
- token
- latency
- maliyet

---

# 11. LITELLM

LiteLLM hemen kurulmayacak.

Aday kullanım:

- provider routing
- budget
- quota
- fallback
- cache

Önce şu kanıtlanmalı:

> Gerçekten birden fazla provider’ı otomatik yönetecek ortak gateway’e ihtiyacımız var mı?

Eğer yalnız:

```text
Codex/OpenAI
+
NVIDIA
```

yeterliyse yeni dependency eklenmez.

Gerçek ihtiyaç varsa:

1. mevcut canonical abstraction genişletilebilir mi?
2. değilse LiteLLM daha temiz mi?

karşılaştırılır.

---

# 12. DİĞER GITHUB ARAÇLARI

Araştırma listesinde tutulacak ancak körlemesine kurulmayacak:

### OpenCode
Provider bağımsız terminal agent.

- [ ] yalnız sandbox altında test
- [ ] root VPS’de unrestricted çalışma yok

### Continue CLI
- [ ] headless/read-only/CI işlerinde değerlendir

### Plandex
- [ ] büyük multi-file plan/diff işlerinde benchmark

### smolagents
- [ ] Harekât Subayı orchestration için ancak mevcut kod yetersizse değerlendir

### Cline
- [ ] alternatif terminal/MCP agent

### Roo Code
Yeni core dependency yapılmayacak; durum implementasyon günü tekrar doğrulanmadan kullanılmayacak.

---

# 13. SANDBOX / AGENT GÜVENLİĞİ

Agent kod yazacak ve shell kullanacaksa host VPS’ye sınırsız bırakılmayacak.

Değerlendirilecek:

### NemoClaw / OpenShell

Amaç:

```text
MODEL
+
CODING HARNESS
+
SANDBOX / POLICY
```

Alpha/erken teknoloji ise önce lab.

Core’a doğrudan gömülmez.

---

# 14. NEMO GUARDRAILS / TOOL POLICY

Tool input/output validation ve agent-action policy için değerlendirilecek.

Hedef permission modeli:

```text
ALLOW / AUTO

git read
rg
pytest
SQLite read
journalctl
system health
external research
report generation
```

```text
REQUIRE APPROVAL

source edit
config edit
persistent DB mutation
service restart
git commit
git push
deployment
```

```text
DENY

private key
seed phrase
wallet signing
live order
self-enable live
Risk Gate bypass
dangerous destructive shell
unapproved privileged action
```

---

# 15. VEZİR’İ GERÇEK OPERASYON AJANINA DÖNÜŞTÜRME

Şu anki Vezir:

```text
soru
 ↓
Groq intent
 ↓
allowlisted intent
 ↓
deterministic answer
```

Bu korunacak ama genişletilecek.

Hedef:

```text
                     SEN
                      │
                    VEZİR
                      │
     ┌────────────────┼────────────────┐
     ▼                ▼                ▼
 CONVERSATION       REPORTS         TASKS
 MEMORY             ADVICE        ORCHESTRATION
     │                │                │
     └────────────────┼────────────────┘
                      ▼
                  EVIDENCE
                      │
    ┌──────┬──────┬───┴───┬──────┬───────┐
    ▼      ▼      ▼       ▼      ▼       ▼
   P3     P5/P7   P9     P10   P11/13   P12
  Risk   Market Wallet  Threat Learning Runtime
```

Vezir bütün Phase’leri sahiplenmez.

Vezir:

**okur → birleştirir → açıklar → tavsiye verir → doğru Phase’e yönlendirir.**

---

# 16. VEZİR — GERÇEK SOHBET

- [ ] doğal multi-turn conversation
- [ ] follow-up understanding
- [ ] bounded context
- [ ] summarization
- [ ] token limit
- [ ] age limit
- [ ] stale-context eviction
- [ ] deterministic fast path
- [ ] provider unavailable fallback
- [ ] prompt injection tests

Örnek:

```text
Sen:
Dün neden trade açmadık?

Vezir:
...

Sen:
Bugün fark ne?

Vezir:
dünkü contexti bilir
+
bugünkü evidence'i getirir
```

---

# 17. VEZİR — HAFIZA

İki farklı hafıza karıştırılmayacak.

## Operatör/proje hafızası — Phase 14

- çalışma kuralları
- aktif task
- canonical kararlar
- kabul/reddedilmiş öneriler
- incident summary
- operator preferences

## Trade öğrenmesi — Phase 11/13

- kazanan/kaybeden
- false positive
- false negative
- missed opportunity
- exit failure
- calibration

Vezir Phase11/13 verisini **okur**.

Kendi kendine threshold/strategy değiştirmez.

Canonical repo/runtime truth her zaman Vezir memory’den üstündür.

---

# 18. VEZİR — RAPOR MERKEZİ

Vezir otomatik rapor üretebilmeli:

```text
RUNTIME
PAPER
RISK
OPPORTUNITY
BLOCKERS
PROVIDER
LEARNING
SECURITY
MAINTENANCE
```

Her raporda üç bölüm:

```text
FACT
ANALYSIS
RECOMMENDATION
```

AI’nın uydurduğu sayı kullanılmaz.

---

# 19. VEZİR — TAVSİYE MOTORU

Vezir:

> “Ne oldu?”

yanında:

> “Ne yapmalıyız?”

sorusuna da cevap verecek.

Öneri formatı:

```text
ISSUE
EVIDENCE
IMPACT
OWNER PHASE/SUBPHASE
RECOMMENDATION
NEXT TEST
```

Öneri:

**trade permission değildir.**

Örnek route:

```text
risk        → Phase 3
lifecycle   → Phase 4/6
market      → Phase 5/7
provider    → Phase 8/12
wallet      → Phase 9
adversary   → Phase 10
learning    → Phase 11/13
operator UI → Phase 14
```

---

# 20. VEZİR — İÇ SİSTEM TEŞHİSİ

Vezir gerektiğinde şunları araştırabilmeli:

- service
- process
- CPU/memory/disk
- journal
- exceptions
- DB integrity
- DB lock
- schema
- candidate blockers
- queue/backpressure
- provider state
- git drift
- dirty tree
- config
- authority
- secret exposure
- tests
- CI
- duplicate/dead code

Çıktı:

```text
PROBLEM
LOCATION
EVIDENCE
IMPACT
OWNER
RECOMMENDED FIX
TEST
```

---

# 21. VEZİR — DIŞ GÜVENLİK / ADVERSARY INTELLIGENCE

Dış kaynaklardan araştırılacak:

- smart-contract exploit
- honeypot
- rug
- liquidity withdrawal
- staged liquidity drain
- MEV/sandwich
- sniper bots
- pump/dump
- sybil/wash
- oracle
- bridge
- wallet drain
- malicious RPC
- dependency supply-chain
- social engineering
- deception/bot tactics

Kaynaklar:

- GitHub
- security advisories
- BNB Chain
- PancakeSwap
- audit/security araştırmaları
- CVE/NVD
- ilgili teknik/akademik kaynaklar
- NVIDIA security/agent research

Vezir yalnız haber toplamayacak.

Akış:

```text
NEW THREAT
    ↓
mechanism
    ↓
Coinoskobi relevant?
    ↓
existing protection?
    ↓
affected file / Phase
    ↓
safe test fixture
    ↓
current defense test
    ↓
COVERED / PARTIAL / EXPOSED / UNKNOWN
```

---

# 22. VEZİR — ROOT CAUSE → KOD → TEST

Vezir gerektiğinde kod hazırlayabilecek.

Yetki sırası:

```text
READ
 ↓
ANALYZE
 ↓
PROPOSE
 ↓
TEST
 ↓
DIFF
 ↓
SECOND REVIEW
 ↓
APPROVAL
 ↓
APPLY
```

Sonraki ayrı kapılar:

```text
COMMIT
PUSH
DEPLOY
```

Vezir çıktısı:

```text
ROOT CAUSE
FILE
FUNCTION
PATCH
TEST
DIFF
PHASE OWNER
AUTHORITY IMPACT
```

Ama:

- risk gate auto-weaken yok
- sellability bypass yok
- hard block bypass yok
- wallet/live enable yok

---

# 23. HAREKÂT SUBAYI — ÇOKLU AI RAPOR BİRLEŞTİRME

Vezir şu kaynaklardan rapor toplayabilir:

```text
ChatGPT
Codex
Copilot
CodeRabbit
NVIDIA
Claude
Gemini
GitHub CI
VPS tests
runtime evidence
```

Yapacağı:

1. aynı bulguları dedup
2. görüşü evidence’dan ayır
3. çelişkileri bul
4. test/runtime evidence ile çözmeye çalış
5. çözülemeyeni açık yaz
6. tek operator summary üret

Model itibarı kanıtın önüne geçmez.

---

# 24. VEZİR COMMAND CENTER

Yeni panel yok.

Mevcut tek canonical Command Center büyütülür.

Vezir alanları:

```text
SOHBET
SİSTEM DURUMU
AKTİF GÖREVLER
PAPER DURUMU
GELEN AI RAPORLARI
VEZİR TAVSİYELERİ
GÜVENLİK ALARMLARI
LEARNING BULGULARI
EVIDENCE
APPROVAL REQUESTS
MODEL / PROVIDER / TOKEN COST
```

Default görünüm kısa.

Teknik detay talep edilince açılır.

---

# 25. TOKEN / COST TELEMETRY

Her AI görevi için mümkün olduğunda:

```text
task type
provider
model
input tokens
output tokens
latency
cache hit
estimated cost
test pass/fail
human acceptance
```

saklanır.

Sonra gerçek veriye göre:

```text
log triage → model A
small patch → model B
security → strong model
critical bug → premium
```

seçilir.

---

# 26. DATA FLYWHEEL

Coinoskobi çözülen her problemden öğrenebilir.

Akış:

```text
INCIDENT
 ↓
EVIDENCE
 ↓
ROOT CAUSE
 ↓
PATCH
 ↓
TEST
 ↓
RUNTIME
 ↓
DB RESULT
 ↓
ACCEPT / REJECT
 ↓
VERIFIED EXAMPLE
```

---

## YouTube / harici strateji fikirlerinden doğrulanacak adaylar

Bu maddeler yeni Phase, yeni runtime veya ikinci strateji motoru oluşturmaz. Önce mevcut implementation aranır; yalnız ölçülebilir ek değer varsa mevcut owner Phase genişletilir.

- [ ] **Phase 7:** mevcut regime/flow kodunu envanterle; HMM veya benzeri rejim modeli eklemeden önce mevcut deterministic rejim sinyalleriyle karşılaştır
- [ ] **Phase 7:** regime state yanında confidence / stability / transition-risk evidence adaylarını ölç
- [ ] **Phase 7:** strateji/entry uygunluğunu rejim evidence ile etiketle; Risk Gate ve hard safety her zaman üstün kalsın
- [ ] **Phase 11/13:** tek canonical deney zinciri kur: `hypothesis → backtest → out-of-sample → walk-forward → PAPER → outcome`
- [ ] **Phase 11:** edge-decay ölçümü ve `RETIRE_CANDIDATE` benzeri proposal-only strateji yaşlanma çıktısını değerlendir
- [ ] **Phase 11/13:** her strateji deneyinde gas / fee / slippage / liquidity / sellability / exit-capacity maliyetlerini zorunlu evidence olarak kullan
- [ ] **Phase 11/13:** aynı stratejinin farklı market regime’lerde sonuçlarını ayrı ölç; tek dönem performansını genelleme
- [ ] **Phase 14:** Vezir deney sonuçlarını okuyup FACT / ANALYSIS / RECOMMENDATION üretsin; threshold/strategy auto-apply yetkisi olmasın
- [ ] **AI mühendislik:** ucuz model tarama/rutin işte, güçlü model zor root-cause/architecture işinde; ikinci model review yalnız riskli değişikliklerde
- [ ] YouTube kâr ekranı, creator iddiası veya TradingView screenshot’u doğrulama evidence sayılmasın; yalnız test edilecek hypothesis kaynağı olsun

# 27. NEMO CURATOR

Dataset büyüyünce değerlendirilir:

- exact dedup
- fuzzy dedup
- semantic dedup
- quality filtering
- decontamination
- dataset preparation

Ama bugün zorunlu dependency değil.

---

# 28. RAG / REPOSITORY MEMORY

Her kod satırı RAG’e verilmez.

Öncelikle local retrieval.

RAG için uygun içerik:

```text
canonical MD
ROADMAP
architecture decisions
old incidents
bug/fix history
DB schema history
runbooks
security rules
GitHub PR decisions
```

Basit lookup → normal retrieval.

Karmaşık multi-document tarihçe → gerekirse agentic RAG.

---

# 29. QLORA / FINE-TUNING

Şimdi yapılmayacak.

Önkoşullar:

- yeterli gerçek incident
- kaliteli root cause
- kabul edilmiş patch
- test sonucu
- runtime sonucu
- temiz dataset
- benchmark

Sonra gerekirse küçük/orta open model Coinoskobi konusunda uzmanlaştırılır.

Ama retrieval/tool-use iyi olmadan fine-tuning başlamaz.

---

# 30. KNOWLEDGE DISTILLATION

Daha ileri safha.

```text
Teacher
strong/premium models
       ↓
verified successful examples
       ↓
Student
small cheap model
       ↓
Coinoskobi-specialized engineering agent
```

Ama ancak dataset/benchmark olgunlaştıktan sonra.

---

# 31. DEAD CODE / CLEANUP

Her implementation turunda:

```text
references
imports
tests
systemd
configs
workflows
runtime usage
```

audit edilir.

Silinecek adaylar:

- duplicate implementation
- superseded module
- stale script
- `.bak`
- disposable probe
- experiment helper
- unused config
- unused test helper
- obsolete AI/provider route

Tarihsel audit evidence korunabilir.

Executable çöp tutulmaz.

---

# 32. SAFE AUTOMATION SINIRLARI

Vezir’in mümkün olduğunca otomatik yapabileceği:

- read
- search
- DB read
- log analysis
- external research
- report
- recommendation
- diagnosis
- controlled test
- read-only review
- benchmark
- token/cost telemetry

Kontrollü/approval:

- source modification
- config modification
- threshold change
- DB write
- service restart
- commit
- push
- deployment

Default yasak:

- private key
- seed
- signing
- live order
- self-enable live
- hard safety bypass

---

# 33. VALIDATION PROTOKOLÜ

Her anlamlı maintenance slice:

```text
OWNER PHASE/SUBPHASE
        ↓
TARGETED IMPLEMENTATION
        ↓
TARGETED TESTS
        ↓
SECURITY / AUTHORITY TESTS
        ↓
SMOKE / E2E
        ↓
FULL REGRESSION gerekiyorsa
        ↓
COMPILE / DB INTEGRITY
        ↓
git diff --check
        ↓
DEAD CODE AUDIT
        ↓
SECOND REVIEW
        ↓
GITHUB
        ↓
VPS SYNC
        ↓
RUNTIME ACCEPTANCE
        ↓
TRACKER UPDATE
```

Kod yazılması completion değildir.

Runtime evidence ile kapanması completion’dır.

---

# 34. CHECKPOINT FORMAT

Her kapanan çalışma sonrası bu tracker güncellenir:

```text
DATE:
ÇALIŞMA ALANI:
OWNER PHASE/SUBPHASE:
TASK:
STATUS:
FILES:
TESTS:
RUNTIME:
GITHUB PR/COMMIT:
AUTHORITY CHANGED:
DEAD CODE REMOVED:
TOKEN/COST EVIDENCE:
NEXT SAFE STEP:
```

Ayrıca:

**PROJECT_STATE.md**
→ mevcut operasyonel truth

**TEST_RESULTS.md**
→ test/audit/runtime validation geçmişi

**planlı yapılacaklar.md**
→ henüz bitmemiş işler + tikler + sıradaki adım

---

# 35. HEDEF SON DURUM

```text
                     SEN
                      │
                      ▼
                   VEZİR
            OPERASYON / HAREKÂT
                      │
       ┌──────────────┼───────────────┐
       │              │               │
   CONVERSATION     REPORTS        SECURITY
   + MEMORY         + ADVICE       + RESEARCH
       │              │               │
       └──────────────┼───────────────┘
                      ▼
               LOCAL EVIDENCE
       git / rg / DB / logs / tests
                      │
                      ▼
                MODEL ROUTING
       local → cheap → mid → strong
                      │
               premium if needed
                      │
                      ▼
             CODING / ANALYSIS
          Codex / NVIDIA / Aider
             + other tools
                      │
                      ▼
               SANDBOX / POLICY
                      │
                      ▼
          EXISTING COINOSKOBI CORE
       Phase 0–15 / deterministic
                      │
             TEST / DB / RUNTIME
                      │
                      ▼
                    GitHub
```

En önemli kural:

> **Vezir Coinoskobi’nin üstünde yeni bir sistem değildir.**
> Vezir mevcut Coinoskobi’nin insanla konuşan, evidence toplayan, analiz eden, araştıran, raporlayan ve mühendislik araçlarını koordine eden Phase 14 katmanıdır.

Trade/risk/runtime sahipliği mevcut Phase’lerde kalır.

---

# 36. HISTORICAL / BACKLOG ÖNCELİK LİSTESİ

> Bu bölüm 2026-09-20 dönemindeki ayrıntılı backlog sırasını korur. Güncel yürütme sırası dosyanın en üstündeki **ACTIVE NOW / NEXT** bölümüdür; aşağıdaki açık kutular otomatik olarak aktif iş anlamına gelmez.

1. [x] **PAPER recovery closure + 2026-09-20 kritik runtime düzeltmeleri**
2. [ ] **Yeni gerçek PAPER işleminde kritik entry/exit/data incidenti çıkarsa onu önce kapat**
3. [ ] **Phase/subphase + dead-code inventory**
4. [ ] **Local evidence/token reducer**
5. [ ] **YouTube/harici fikir adaylarını mevcut Phase 7 / 11 / 13 / 14 koduyla karşılaştır; duplicate yaratma**
6. [ ] **Rejim / experiment-lifecycle / edge-decay adaylarından yalnız ölçülebilir olanları shadow/backtest planına al**
7. [ ] **Codex↔NVIDIA read-only benchmark**
8. [ ] **Aider düşük-token benchmark**
9. [ ] **Model/cost telemetry**
10. [ ] **Gerekliyse routing/fallback**
11. [ ] **Vezir gerçek conversation**
12. [ ] **Vezir memory**
13. [ ] **Vezir reports/recommendations**
14. [ ] **Vezir internal health/security**
15. [ ] **Vezir external adversary research**
16. [ ] **Vezir root-cause/code/test**
17. [ ] **Harekât Subayı multi-agent report ingestion**
18. [ ] **Command Center UX**
19. [ ] **Sandbox/policy hardening**
20. [ ] **Data Flywheel**
21. [ ] **RAG gerekiyorsa**
22. [ ] **Dataset/Curator gerekiyorsa**
23. [ ] **QLoRA ancak veri yeterliyse**
24. [ ] **Distillation daha sonra**
25. [ ] **final cleanup / regression / seal**

---

# PHASE 15H — EXECUTION-GRADE PAPER SIMULATION

**Owner:** Phase 15H only for transaction-level simulation engine/evidence production.

Non-overlap contract:
- Phase 3 owns risk/sellability/admission interpretation.
- Phase 4/6 own position/exit lifecycle decisions.
- Phase 8 owns canonical RPC/WSS/provider transport and resilience.
- Phase 10 owns MEV/adversary detection/classification.
- Phase 11/13 own learning/calibration/outcome memory.
- Phase 12 owns operational PAPER runtime, DB lifecycle and E2E composition.
- Phase 14 owns panel/Vezir/operator projection.
- Phase 15A–15G own drift adapter/comparison/composition/classification/projection/safety boundaries.
- 15H owns only non-broadcast execution sandbox + raw simulated BUY/SELL outcome evidence.

Checklist:
- [x] 15H canonical ownership and non-overlap boundary opened
- [x] existing execution/simulation/provider/router implementation reference audit
- [x] choose smallest deterministic simulation backend while preserving Phase 8 provider/resilience ownership; current Anvil fork bootstrap uses configured RPC URL directly
- [x] explicit-block simulated BUY with received amount/revert/gas/receipt evidence; unsupported/unmeasured slippage/fill remains UNKNOWN
- [x] lifecycle-requested simulated SELL with received quote/revert/gas/receipt evidence; unsupported/unmeasured slippage/fill remains UNKNOWN
- [x] BUY/SELL provenance and UNKNOWN-preserving result contract; stateful BUY→SELL continuity is not claimed unless directly proven by implementation evidence
- [x] bind 15H output through existing Phase 15B adapter; do not duplicate 15A–15G
- [x] authority tests: no broadcast, no private key, no wallet/signing/live/order-create, no Risk Gate override
- [x] targeted tests + integration smoke + runtime acceptance
- [x] canonical docs/test evidence seal after acceptance

# HISTORICAL NEXT SAFE STEP

> Bu bölüm eski continuation sırasını korur ve artık current instruction değildir. Güncel sıra dosyanın en üstündeki **ACTIVE NOW / NEXT** bölümüdür.

**Tarihsel Öncelik 1:** AUTO PAPER çalışırken ortaya çıkan gerçek kritik entry / exit / data incidentlerini hedefli biçimde kapat. Normal piyasa zararı tek başına bug/tuning gerekçesi değildir.

Aktif kritik incident yoksa:

**Repository / Phase-subphase / dead-code inventory.**

Ardından:

**Local evidence / token reducer.**

YouTube/harici kaynaklardan çıkarılan regime, walk-forward, experiment lifecycle ve edge-decay fikirleri tracker’a eklenmiştir; **envanter ve mevcut implementation karşılaştırması yapılmadan kodlanmaz.**

Yeni AI/Vezir implementationı da repository inventory tamamlanmadan başlamaz.
