# COINOSKOBI — WALLET & TOKEN INTELLIGENCE FUTURE BACKLOG

Status: **PLANNED / NOT STARTED**

Bu belge numaralandırılmış Phase 0–15 roadmap'ini genişletmez ve Phase 16 açmaz.
Amaç, post-roadmap dönemde değerlendirilecek wallet universe + token identity + birleşik evidence graph fikrini kaybetmeden planlı biçimde korumaktır.

Bu backlog hiçbir decision, paper, live, wallet-signing veya execution authority oluşturmaz.

---

# 1. Amaç

Coinoskobi'nin yalnız token/pool hareketini değil, hareketi oluşturan wallet aktörlerini ve tokenın dış kimlik kanıtlarını da ayrı evrenler olarak gözlemlemesi.

Hedef üç bağımsız intelligence katmanını daha sonra birleştirmektir:

1. **Token / Pool Universe** — mevcut COLD / WARM / HOT seismic market evreni.
2. **Wallet Universe** — başarılı ve davranışsal olarak önemli walletların COLD / WARM / HOT gözlem evreni.
3. **Token Identity / Social Universe** — website, X/Twitter, Telegram, Discord ve diğer proje kimlik kanıtları.

Final hedef tek bir sinyal üretmek değil, bağımsız kanıtların aynı fırsatı destekleyip desteklemediğini ölçmektir.

---

# 2. Wallet Universe — “Cüzdan Tokenoskobisi”

## 2.1 Wallet discovery

Muhtemel kaynaklar:

- gerçek DEX swap transaction origin (`transaction.from`)
- mevcut Phase 9 wallet/entity evidence
- geçmişte başarılı tokenlara erken giren walletlar
- gözlenen HOT/WARM tokenların alıcı/satıcı walletları
- güvenilir harici wallet-label kaynakları, yalnız provenance ile

Harici label hiçbir zaman otomatik güven veya trade izni değildir.

## 2.2 Wallet registry

Her wallet chain-aware kimlikle tutulur.

Temel alanlar:

- chain
- wallet address
- first_seen / last_seen
- activity count
- observed token count
- realized/unrealized outcome evidence mevcutsa provenance
- early-entry count
- repeated-success count
- loss / scam exposure evidence
- current wallet state
- confidence
- freshness

## 2.3 Wallet COLD / WARM / HOT modeli

### COLD

Registry'de bilinen fakat şu an özel davranış göstermeyen wallet.
Ucuz ve seyrek observation.

### WARM

Normal davranışına göre anlamlı aktivite artışı gösteren wallet.
Örnek evidence:

- yeni tokenlara normalden erken giriş
- accumulation artışı
- işlem sıklığında anomalik artış
- geçmişte başarılı olduğu davranış tipinin tekrar oluşması
- bağımsız başarılı walletlarla aynı tokena yönelme

### HOT

Yeterli geçmiş kanıtı olan ve mevcut davranışı yüksek öncelikli görünen wallet.
Örnek evidence:

- tekrar eden erken fırsat başarısı
- yeni fırsatta güçlü ve zamanında pozisyon alma
- yüksek confidence smart-money davranışı
- birkaç bağımsız HOT walletın aynı token üzerinde birleşmesi

Wallet HOT olmak tek başına token entry izni vermez.

## 2.4 Wallet behavior personas

Walletlar tek “iyi/kötü” skora sıkıştırılmaz.
Davranış profilleri ayrı tutulabilir:

- early hunter
- momentum follower
- dip buyer
- launch sniper
- fast flipper
- medium/long holder
- distribution-heavy wallet
- repeat scam victim
- repeat successful new-token participant

Başarı bağlama göre ölçülür. Örneğin “genel olarak başarılı wallet” yerine “yeni Pancake tokenlarında ilk 30 dakikada başarılı wallet” daha değerlidir.

---

# 3. Wallet Relationship / Cluster Evidence

Amaç walletlar arasında olası bağlantıları kanıt ağı olarak tutmaktır.

Muhtemel evidence:

- direct funding
- common funder
- repeated coordinated timing
- repeated common counterparties
- aynı tokenlarda olağandışı eşzamanlı davranış
- bridge/CEX funding context
- transfer graph evidence

Kesin kural:

**same funder != same owner**

**aynı davranış != aynı kişi**

Bu nedenle “alt cüzdan” kesin kimlik iddiası olarak değil, confidence/provenance taşıyan ilişki evidence'i olarak modellenir.

CEX, bridge, router ve contract walletlar false-link üretmemesi için ayrı sınıflandırılır.

Hot path graph traversal yapmaz; ilişki sonucu precomputed bounded readmodel üzerinden okunur.

---

# 4. Token Identity / Social Intelligence

Token/pool için mevcut market verisine ek olarak proje kimliği evidence'i tutulur.

Muhtemel kaynaklar:

- DexScreener token metadata
- official website
- X/Twitter
- Telegram
- Discord
- diğer doğrulanabilir proje bağlantıları

## 4.1 Identity evidence

Tutulabilecek bilgiler:

- link existence
- domain age / consistency daha sonra değerlendirilebilir
- sosyal hesap yaşı
- sosyal hesap/token adı/adres tutarlılığı
- resmi kaynakların birbirine referans vermesi
- duplicate/copied website evidence
- abandoned/dead social evidence
- account activity/freshness

## 4.2 Safety kuralları

- website varlığı = gerçek proje değildir
- sosyal hesap varlığı = güven değildir
- follower sayısı tek başına kalite değildir
- missing social = otomatik scam değildir
- metadata provider failure = token hakkında negatif kanıt değildir
- external/social fetch hot path'i bloke etmez

Bu katman identity confidence / project-presence evidence üretir; hard safety'yi override etmez.

---

# 5. Token ↔ Wallet Unified Evidence Graph

Uzun vadeli en değerli birleşim:

`Token/Pool <-> Wallet <-> Wallet Cluster <-> Project Identity`

Amaç tokenı yalnız fiyat hareketinden değil, onu hareket ettiren aktörlerden ve proje kimliğinden de değerlendirmektir.

Örnek yüksek değerli birleşim:

- token seismic HOT
- birden fazla bağımsız HOT wallet accumulation
- walletların ilgili davranış tipinde geçmiş başarı evidence'i
- liquidity/sellability sağlıklı
- token identity/social evidence tutarlı

Örnek erken uyarı birleşimi:

- token henüz COLD/WARM
- birkaç güçlü wallet erken accumulation başlatıyor
- walletlar birbirinden bağımsız
- proje kimlik evidence'i mevcut
- seismic henüz hareketi tam yakalamamış

Bu durumda wallet intelligence, market hareketinden önce bir **early-warning observation** üretebilir.

Tersi de mümkündür:

- token HOT
- görünen çoklu walletlar aynı funder/cluster çevresinde
- sosyal/web kimliği zayıf veya tutarsız
- participation bağımsız görünmüyor

Bu durumda HOT hareket “yüksek kalite fırsat” yerine “şüpheli/koordineli hareket” olarak downgrade edilebilir.

---

# 6. Birleşik Evidence Sınıfları — Taslak

İleride kullanılabilecek advisory sınıflar:

- MARKET_ONLY
- WALLET_EARLY_WARNING
- WALLET_CONFIRMED
- MULTI_HOT_WALLET_CONVERGENCE
- IDENTITY_CONFIRMED_CONTEXT
- FULL_CONVERGENCE
- COORDINATED_OR_SUSPICIOUS
- CONFLICT
- UNKNOWN

Bu isimler şimdilik taslaktır; implement kararı değildir.

---

# 7. Learning / Outcome Bağlantısı

Yeni wallet ve identity evidence ancak outcome ile ölçülürse anlamlıdır.

Daha sonra Phase 11/13 learning ilkeleri reuse edilmelidir:

- wallet sinyali sonrası 5m / 15m / 30m / 60m outcome
- wallet early-warning lead time
- token seismic'e göre kaç saniye/dakika erken sinyal verdiği
- false-positive wallet convergence
- missed opportunity
- avoided loss
- wallet persona bazında hit-rate
- wallet cluster bazında başarı/yanılma
- social/identity evidence'in outcome ile ilişkisi

Minimum sample guard zorunludur.

Auto-threshold, auto-weight veya self-modifying strategy yoktur; learning proposal-only kalır.

---

# 8. Önerilen Uygulama Sırası

Bu backlog implement edilmeye karar verilirse önerilen sıra:

### A — Read-only Wallet Universe Baseline

- mevcut gerçek tx.from evidence'inden wallet registry
- bounded discovery
- wallet history/outcome baseline
- hiçbir strategy etkisi yok

### B — Wallet State Model

- COLD / WARM / HOT tanımı
- cadence
- minimum sample guards
- wallet outcome validation

### C — Wallet Relationship Evidence

- funding / common-funder / coordination evidence
- CEX/router/bridge false-link guards
- confidence ve UNKNOWN davranışı

### D — Token Identity Metadata

- DexScreener metadata adapter
- website / X / Telegram / Discord link registry
- freshness / provenance / bounded cache

### E — Identity Quality Evidence

- link consistency
- project-presence confidence
- stale/missing/contradictory evidence

### F — Token ↔ Wallet Fusion Readmodel

- token state + wallet state + cluster evidence + identity evidence
- advisory-only convergence/conflict output

### G — Counterfactual / Outcome Validation

- wallet lead-time
- matched-control
- false-positive / false-negative
- minimum sample gate

### H — Production Binding

Yalnız evidence yeterliyse mevcut candidate prioritization/readmodel katmanına bounded advisory input.
Hot path raw graph veya social provider beklemez.

---

# 9. Başlamadan Önce Zorunlu Kabul Kriterleri

Implement kararı verilmeden önce:

- mevcut Phase 9 wallet intelligence ile overlap analizi
- mevcut universe scheduler/readmodel reuse planı
- provider/API maliyet analizi
- DB büyüme tahmini
- hot-path latency bütçesi
- wallet false-attribution risk matrisi
- DexScreener metadata kullanım sınırları
- social provider provenance/freshness modeli
- minimum sample/outcome planı

Yeni duplicate pipeline kurulmamalıdır.
Mevcut wallet/entity, universe, learning ve bounded scheduler altyapıları mümkün olduğunca reuse edilmelidir.

---

# 10. Authority / Safety Sınırı

Bu backlog tamamen intelligence/observation/advisory kapsamıdır.

- wallet private key yok
- signing yok
- transaction create yok
- live execution yok
- automatic trade authority yok
- automatic threshold apply yok
- automatic weight apply yok
- identity guessing yok
- wallet ownership kesin iddiası yok
- hard safety override yok

Wallet intelligence ile wallet authority aynı şey değildir.

---

# 11. Başarı Tanımı

Başarılı bir gelecek implementasyonu şu soruları ölçülebilir biçimde cevaplayabilmelidir:

**“Hangi walletlar belirli fırsat tiplerinde gerçekten başarılı?”**

**“Bu walletlar şu anda hangi tokenlarda birleşiyor?”**

**“Wallet hareketi token seismic hareketinden anlamlı şekilde önce geliyor mu?”**

**“Görünen çoklu wallet hareketi gerçekten bağımsız mı, yoksa aynı cluster mı?”**

**“Tokenın project identity/social kanıtı bu fırsatı destekliyor mu, çelişiyor mu?”**

**“Market + Wallet + Identity birlikte olduğunda outcome, tek başına market sinyalinden daha iyi mi?”**

Bu sorular gerçek outcome evidence ile cevaplanmadan sistemin strategy thresholdları değiştirilmez.
