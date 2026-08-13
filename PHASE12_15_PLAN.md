# COINOSKOBI — PHASE 12–15 FINAL ROADMAP

Bu belge Phase 11 + OCR kapanışı sonrasında Phase 12–15 için alınmış resmi kararları kilitler.

## Aktif durum

- Phase 11: ✅ CLOSED
- OCR: ✅ CLOSED
- Phase 12: 🟡 ACTIVE
- Phase 13: ⏳ WAITING
- Phase 14: ⏳ WAITING
- Phase 15: ⏳ WAITING / FINAL ROADMAP PHASE
- Phase 12 başlangıç baseline: **873 PASS**
- İlk operasyonel hedef: **sistemi gerçek runtime ile tamamlayıp PAPER TRADE'e geçirmek**

Phase 12'nin ilk işi yeni özellik eklemek değil; paper trade için gerçek runtime readiness durumunu deterministik olarak ölçmek ve yalnız gerçek blocker'ları kapatmaktır.

## Roadmap sınırı

- Phase 12–15 mevcut numaralı roadmap'in son bölümüdür.
- Phase 15 final roadmap fazıdır.
- Phase 16, Era, V2 veya V3 otomatik olarak açılmaz.
- Phase 15 sonrasında gerçek kullanımda bulunan eksik, düzeltme ve iyileştirmeler ilgili fazın altında patch/hotfix/maintenance olarak yürütülür.
- Yeni numara üretmek yerine çalışan sistemi ölçmek, düzeltmek ve iyileştirmek esastır.

## Çeviklik ve güvenlik doktrini

Coinoskobi güvenli olacaktır; fakat güvenlik adına paranoyak, korkak veya hantal hale getirilmeyecektir.

- Güvenlik mümkün olduğunca basit, deterministik, ucuz ve kanıtlanmış yöntemlerle sağlanır.
- Hard block yalnız ağır ve doğrulanabilir risklerde kullanılır.
- Soft riskler otomatik hard block'a çevrilmez; score, confidence, WATCH, sizing veya manuel değerlendirme ile yönetilir.
- Hot path'e gereksiz DB aggregate, raw-history scan, AI/provider beklemesi veya tekrarlı ağır doğrulama eklenmez.
- Ağır işler bounded slow path'te; hızlı karar için gerekli veri precomputed/readmodel/cache hattında tutulur.
- Aynı riski kapsayan duplicate guard/state/pipeline oluşturulmaz.
- Yeni koruma eklenmeden önce gerçek risk, ölçüm, mevcut korumanın yetersizliği ve latency/complexity maliyeti sorgulanır.
- Paper/live evidence bir guard'ın kaliteli fırsatları gereksiz öldürdüğünü gösterirse guard gözden geçirilir, gevşetilir veya kaldırılır.
- Amaç hiç kaybetmemek değil; kötü kayıpları sınırlarken kaliteli fırsatları hızlı yakalamaktır.
- Hız güvenliğin düşmanı değildir; güvenlik hızlı mimarinin içine gömülür.

Takip edilecek önemli kalite metriği: Opportunity Kill Rate — güvenlik/filtre kararlarının sonradan kaliteli olduğu görülen kaç fırsatı gereksiz yere elediği.

---

# PHASE 12 — Operational Paper-Trade Readiness

## Status

🟡 ACTIVE

## Ana hedef

Sistemi gerçek kaynaklarla uçtan uca çalışır hale getirip güvenilir PAPER TRADE operasyonuna geçirmek.

Phase 12'nin başarı tanımı yeni özellik sayısı değildir. Başarı: gerçek runtime verisiyle adayın keşiften paper pozisyon kapanışına kadar aynı application lifecycle içinde izlenebilir ve tekrarlanabilir şekilde ilerlemesidir.

## İlk iş sırası

### 12A — Paper Readiness Preflight

- production composition root kontrolü
- WSS config + market-flow binding kontrolü
- paper lifecycle binding kontrolü
- paper DB/schema availability
- outcome-learning feed availability
- authority sınırlarının kapalı olduğunu doğrulama
- blocker listesi üretme
- hot path'e iş eklemeyen startup/read-only preflight

### 12B — Real Runtime Paper Smoke

12A READY olduktan sonra:

- gerçek scanner/cache candidate
- gerçek configured WSS/native context
- market/flow + actor intelligence
- risk/decision
- paper admission
- gerçek paper DB OPEN
- position manager CLOSE
- outcome → learning

aynı application lifecycle içinde doğrulanır.

### 12C — Paper Operation Start

Smoke PASS sonrası sistem kontrollü paper modunda sürekli çalıştırılır. Bu noktadan sonra Phase 12'nin ana işi yeni guard eklemek değil gerçek davranışı ölçmektir.

## Kapsam

1. Gerçek runtime kaynaklarının production composition root altında doğrulanması.
2. Scanner → ingress → bounded queue → analysis → intelligence → risk/safety → decision → paper admission → paper lifecycle zincirinin tek akışta çalışması.
3. WSS/native event, market/flow ve wallet/entity/adversary context'in paper kararına doğru bağlanması.
4. Paper entry/exit lifecycle'ın gerçek opening context ile kayıt altına alınması.
5. SL/TP, trailing/exit, sellability/liquidity ve execution-cost varsayımlarının paper sonuçlarında korunması.
6. Paper outcome → Phase 11 learning feed zincirinin gerçek paper kapanışlarıyla beslenmesi.
7. Restart/recovery, bounded memory, DB integrity ve runtime health doğrulaması.
8. Provider/cost bütçesi: local/cache/free-first; pahalı çağrı bounded ve gerekçeli.
9. Minimum operability görünürlüğü: hangi token, neden aday, giriş var mı, engel ne, SL/TP, beklenen maliyet/PnL, paper sonucu.
10. Gereksiz script/artifact/log üretmeden temiz runtime işletimi.

## Phase 12 sınırları

- Gerçek para YOK.
- Wallet signing YOK.
- Live execution YOK.
- Learning auto-apply YOK.
- AI authority YOK.
- Paper trade gerçek runtime evidence ile çalışabilir.

## Phase 12 kapanış kriteri

Sistem yeterli süre gerçek runtime altında stabil çalışır; paper trade açar/kapatır; sonuçları outcome memory/learning hattına taşır; restart/recovery ve DB bütünlüğünü korur; hot path ölçümlerinde kabul edilemez hantallık görülmez. Bundan sonra ana çalışma paper sonuçlarını toplamaya geçer.

---

# PHASE 13 — Paper Outcome Learning & Calibration

## Ana hedef

Phase 12'de oluşan gerçek paper sonuçlarını kullanarak sistemin nerede iyi, nerede kötü karar verdiğini ölçmek ve fırsat kaçırma/kötü işlem dengesini iyileştirmek.

## Kapsam

- VALID_SIGNAL / FALSE_POSITIVE / FALSE_NEGATIVE / AVOIDED_LOSS / MISSED_OPPORTUNITY / EXIT_FAILURE gerçek outcome analizi.
- False-negative ve missed-opportunity özellikle korunur; sistem yalnız kayıptan korkmayı öğrenmez.
- Opportunity Kill Rate ve avoided-loss dengesi ölçülür.
- Entry/exit, SL/TP, sellability, liquidity, gas, slippage, MEV ve quote-delay etkileri değerlendirilir.
- Market regime, wallet/entity, adversary ve flow attribution sonuçlarla karşılaştırılır.
- Calibration/threshold/weight değişiklikleri proposal-only kalır; yeterli sample olmadan güçlü değişiklik yapılmaz.
- Memory bounded/TTL/rolling-window/pruning ile tutulur; hot path şişirilmez.

## Kapanış kriteri

Yeterli paper evidence ile tekrarlanan hata/fırsat kaçırma sınıfları görünür hale gelir ve uygulanacak değişiklikler ölçülebilir proposal olarak üretilebilir.

---

# PHASE 14 — Command Center & AI Analyst

## Ana hedef

Operatörün birkaç saniyede "hangi token, giriş var mı, neden, SL/TP nerede, vur-kaç uygun mu, paper sonucu ne, engel ne, onay gerekiyor mu?" sorularını cevaplayabildiği kapalı Command Center oluşturmak.

## Kapsam

- Candidate fırsat listesi ve önceliklendirme.
- Atış Poligonu paper/simulation görünümü.
- Vur-Kaç tactical görünümü.
- Entry plan, exit plan, SL/TP, risk/reward ve net expected PnL.
- Gas/slippage/MEV/exit-cost ve sellability/liquidity görünürlüğü.
- Flow, wallet/entity, adversary, news/social/launch context'in sade karar özeti.
- News/social/X/Telegram/Discord, listing/delisting, ICO/IDO/launchpad/airdrop radarının bounded ve source-trust kontrollü entegrasyonu; hot path bu kaynakları beklemez.
- AI contract analyst ve panel assistant: açıklar, uyarır, soruları cevaplar, özetler ve proposal üretir.
- Local/free/cache-first AI; pahalı model yalnız gerçekten değerli ağır analizde.
- AI trade/sign/apply/hardblock-override authority taşımaz.

## Kapanış kriteri

Panel karar desteğini sade ve hızlı verir; paper/runtime truth ile uyumludur; AI açıklayıcı/analisttir, otorite değildir; UI veya AI hot path'i yavaşlatmaz.

---

# PHASE 15 — Final Operational Validation & Controlled Micro-Live

## Ana hedef

Paper varsayımları ile gerçek execution koşulları arasındaki farkı ölçmek ve yalnız açık kullanıcı onayıyla çok küçük kontrollü gerçek para doğrulamasına hazırlanmak/uygulamak.

## Kapsam

- Simulation Drift Validator: theoretical/paper PnL ile gerçekçi gas, slippage, fill, quote delay ve execution timing karşılaştırması.
- Signal-to-block latency/time-drift guard: haber/social sinyali geldiğinde onchain durumun çoktan değişip değişmediğinin kontrolü.
- Paper → micro-live drift ölçümü.
- Entry/exit başarısı, sellability, realized slippage, gas, MEV ve execution latency ölçümü.
- Çok küçük sermaye, açık limitler ve kill-switch.
- Wallet/signing/live authority yalnız bu fazda, ayrı açık kullanıcı onayıyla ve minimum kapsamla açılabilir.
- Paper ve live sonuçları ayrı tutulur; live sonuç paper varsayımını kalibre etmek için evidence olur.
- Gerçek kullanımda çıkan düzeltmeler ilgili faz altında patch/hotfix olarak yapılır; yeni faz açılmaz.

## Final kapanış kriteri

Coinoskobi gerçek veriyle çalışan, paper sonuçlarıyla öğrenen, operatöre hızlı karar desteği veren ve gerçek execution davranışı ölçülmüş bir sistemdir. Phase 15 kapanınca numbered roadmap kapanır.

---

# Uygulama sırası

Şu anki tek aktif hedef **PHASE 12**'dir.

Öncelik sırası:

1. Runtime truth ve production composition doğrulaması.
2. Uçtan uca paper-trade readiness.
3. Gerçek paper trade başlatma.
4. Yeterli outcome toplama.
5. Phase 13 learning/calibration.
6. Phase 14 Command Center/AI.
7. Phase 15 final operational validation ve yalnız açık onayla micro-live.

Bir sonraki faz, mevcut fazın kapanış kriterleri gerçekten sağlanmadan açılmaz.
