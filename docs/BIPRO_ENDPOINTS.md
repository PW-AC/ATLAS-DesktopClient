# BiPRO Endpoints - Deutsche Versicherer

**Stand:** Februar 2026  
**Hinweis:** BiPRO-Endpoints werden von Versicherern typischerweise nicht öffentlich dokumentiert. Diese Liste basiert auf Recherche und bekannten Informationen.

---

## Verifiziert & Funktionierend

### Degenia ✅

| Service | URL | Status |
|---------|-----|--------|
| **STS (410)** | `https://transfer.degenia.de/X4/httpstarter/ReST/BiPRO/410_STS/UserPasswordLogin_2.6.1.1.0` | ✅ Funktioniert |
| **Transfer (430)** | `https://transfer.degenia.de/X4/httpstarter/ReST/BiPRO/430_Transfer/Service_2.6.1.1.0` | ✅ Funktioniert |

**Authentifizierung:** STS-Token-Flow (UsernameToken → SecurityContextToken)  
**Unterstützte Normen:** 430.1, 430.2, 430.4, 430.5  
**Besonderheiten:** `<tran:BestaetigeLieferungen>true</tran:BestaetigeLieferungen>` ERFORDERLICH  
**Ansprechpartner:** Viktor Kerber (viktor.kerber@degenia.de)

---

### VEMA ✅

| Service | URL | Status |
|---------|-----|--------|
| **STS (410)** | `https://bipro.vemaeg.de/va/UserPasswordLogin_2.6.1.1.0` | ✅ Funktioniert |
| **Transfer (430)** | `https://bipro.vemaeg.de/va/TransferService_2.6.1.1.0` | ✅ Funktioniert |

**Authentifizierung:** STS-Token-Flow (VEMA-spezifisches Format)  
**Consumer-ID:** ERFORDERLICH (Format: `XXX_XXXXX`, z.B. `046_11077`)  
**Besonderheiten:**
- Leerer SOAPAction-Header (`""`)
- STS-Request mit `wsa:Action` Header
- KEIN `<tran:BestaetigeLieferungen>` Element
- Response-Namespaces: `t:`, `n:`, `a:` statt `tran:`, `nac:`, `allg:`

**Dokumentation:** https://bipro.vemaeg.de/va/dokumentation (Login: dokumentation / mvp)

---

## Bekannte Endpoints (nicht verifiziert)

### Barmenia

| Service | URL | Quelle |
|---------|-----|--------|
| Leben (Ws 2.1.5) | `https://ws0.barmenia24.de/ibis/services/lebenservice_2.1.5.1.2?wsdl` | StackOverflow |

**Hinweis:** Endpoint aus 2016, möglicherweise veraltet.

---

## BiPRO-Hub Teilnehmer

Der **BiPRO-Hub** (www.biprohub.eu) ist eine zentrale Plattform, über die viele Versicherer erreichbar sind.

### Bestätigte Hub-Teilnehmer

| Versicherer | 430.4 | 430.1/2 | 430.5 | 430.7 |
|-------------|-------|---------|-------|-------|
| **Allianz** | ✅ | ✅ | ✅ | ✅ |
| **AXA** | ✅ | ✅ | ✅ | ✅ |
| **Barmenia** | ✅ | ✅ | ✅ | - |
| **ERGO** | ✅ | ✅ | ✅ | - |
| **Gothaer** | ✅ | ✅ | ✅ | - |
| **HDI** | ✅ | ✅ | ✅ | - |
| **R+V** | ✅ | ✅ | ✅ | - |
| **Signal Iduna** | ✅ | ✅ | ✅ | - |
| **Volkswohl Bund** | ✅ | ✅ | - | - |
| **ALH Gruppe** | ✅ | ✅ | - | - |

**Hub-Katalog:** https://www.biprohub.eu/catalog

---

## Weitere VUs mit BiPRO-Unterstützung

Basierend auf Recherche bieten folgende Versicherer BiPRO-Services an:

### Große VUs

| Versicherer | BiPRO-Normen | Zugang |
|-------------|--------------|--------|
| **Versicherungskammer Bayern** | 430, 440 | Maklerportal |
| **Die Bayerische** | 410, 430.1, 430.4, 430.5, 430.7, 440 | Beraterportal |
| **Zurich** | 430 | Maklerweb |
| **Hanse Merkur** | 430 | Vertriebsportal |
| **BGV** | 430 | Maklerportal |
| **InterRisk** | 430 | Antrag notwendig |
| **Ammerländer** | 430 | bipro.ammerlaender-versicherung.de |

### Pools & Verbünde

| Organisation | Rolle | Hinweis |
|--------------|-------|---------|
| **VEMA** | Pool | Stellt Credentials für angebundene VUs bereit |
| **Fonds Finanz** | Pool | BiPRO-Schnittstellen verfügbar |
| **Blau Direkt** | Pool | BiPRO-Integration |

---

## Typische URL-Muster

Basierend auf bekannten Endpoints folgen viele VUs diesen Mustern:

```
# STS (Authentifizierung)
https://[subdomain].[vu].de/[path]/BiPRO/410_STS/[version]

# Transfer Service
https://[subdomain].[vu].de/[path]/BiPRO/430_Transfer/[version]

# Beispiele:
https://transfer.degenia.de/X4/httpstarter/ReST/BiPRO/430_Transfer/Service_2.6.1.1.0
https://ws0.barmenia24.de/ibis/services/lebenservice_2.1.5.1.2
https://bipro.ammerlaender-versicherung.de/...
```

---

## Authentifizierungs-Methoden

| Methode | Beschreibung | VUs |
|---------|--------------|-----|
| **STS-Token (410)** | UsernameToken → SecurityContextToken | Degenia, VEMA |
| **TGIC-Zertifikat** | X.509-Zertifikat von easy Login | Diverse |
| **VDG-Ticket** | Vermittler-Datenaustausch-Gesellschaft | Diverse |
| **Basic Auth** | Username/Password direkt | Manche |

---

## ⚠️ VU-SPEZIFISCHES VERHALTEN (KRITISCH!)

### Grundprinzip

**JEDE Versicherungsgesellschaft (VU) implementiert BiPRO unterschiedlich!**

Obwohl BiPRO ein Standard ist, gibt es erhebliche Unterschiede in:
- SOAP-Request-Formaten
- Authentifizierungsabläufen
- Pflichtfeldern und optionalen Feldern
- Namespace-Präfixen in Responses
- SOAPAction-Header-Anforderungen

### Design-Regel

```
ÄNDERUNGEN FÜR EINE VU DÜRFEN NIEMALS ANDERE VUs BEEINFLUSSEN!

Beispiel: Eine Änderung am Allianz-Abruf darf NICHTS am AXA-Abruf ändern.
```

### Bekannte VU-Unterschiede

| Eigenschaft | Degenia | VEMA | Standard |
|-------------|---------|------|----------|
| **SOAPAction-Header** | Leer (`""`) | Leer (`""`) | Spezifisch |
| **STS-Request-Format** | Standard BiPRO | VEMA-spezifisch (wsa:Action) | Variiert |
| **Consumer-ID** | Nicht verwendet | **ERFORDERLICH** | Je nach VU |
| **BestaetigeLieferungen** | **ERFORDERLICH** | Nicht senden | Je nach VU |
| **Response-Namespace** | `tran:`, `nac:` | `t:`, `n:`, `a:` | Variiert |

### Degenia-Spezifika

```xml
<!-- STS: Standard BiPRO -->
<wst:RequestSecurityToken>
   <wst:TokenType>...</wst:TokenType>
   <nac:BiPROVersion>2.6.1.1.0</nac:BiPROVersion>
</wst:RequestSecurityToken>

<!-- listShipments: BestaetigeLieferungen ERFORDERLICH -->
<tran:Request>
   <nac:BiPROVersion>2.6.1.1.0</nac:BiPROVersion>
   <tran:BestaetigeLieferungen>true</tran:BestaetigeLieferungen>
</tran:Request>
```

### VEMA-Spezifika

```xml
<!-- STS: VEMA-Format mit wsa:Action -->
<soapenv:Header>
   <wsa:Action>http://schemas.xmlsoap.org/ws/2005/02/trust/RST/SCT</wsa:Action>
   <wsse:Security soapenv:mustUnderstand="1">...</wsse:Security>
</soapenv:Header>
<RequestSecurityToken xmlns="http://schemas.xmlsoap.org/ws/2005/02/trust">
   <!-- KEIN nac:BiPROVersion! -->
</RequestSecurityToken>

<!-- listShipments: Consumer-ID ERFORDERLICH, KEIN BestaetigeLieferungen -->
<tran:Request>
   <nac:BiPROVersion>2.6.1.1.0</nac:BiPROVersion>
   <nac:ConsumerID>046_11077</nac:ConsumerID>
   <!-- KEIN BestaetigeLieferungen! -->
</tran:Request>
```

### Neue VU hinzufügen

1. **VU-Erkennung implementieren** in `transfer_service.py`:
   ```python
   def _detect_allianz(self) -> bool:
       if 'allianz' in self.credentials.vu_name.lower():
           return True
       return False
   ```

2. **VU-spezifische Logik** in den Methoden:
   ```python
   if self._is_allianz:
       # Allianz-spezifisches Format
   elif self._is_vema:
       # VEMA-spezifisches Format
   else:
       # Standard/Degenia Format
   ```

3. **Dokumentation aktualisieren** (diese Datei)

4. **Tests hinzufügen** für die neue VU

### Code-Referenz

Siehe `src/bipro/transfer_service.py` für die Implementierung:
- `_detect_vema()` - VU-Erkennung
- `_get_soap_action()` - VU-spezifischer SOAPAction-Header
- `_get_sts_token()` - VU-spezifisches STS-Format
- `list_shipments()` - VU-spezifische Request-Felder

---

## Wie komme ich an Endpoints?

### 1. BiPRO-Hub nutzen
- Registrierung bei BiPRO Service GmbH (bipro-service.gmbh)
- Zugang zum Hub-Katalog
- Zentrale Anbindung an viele VUs

### 2. Direkt bei VU anfragen
- Kontakt über Maklerportal des VUs
- Technischer Support / BiPRO-Abteilung anfragen
- Oft ist ein Partnervertrag erforderlich

### 3. Über Pool anfragen
- VEMA, Fonds Finanz, Blau Direkt etc.
- Pools haben oft bestehende Anbindungen
- Credentials werden vom Pool bereitgestellt

### 4. easy Login nutzen
- Zentrales Zertifikatsmanagement
- Vereinfachter Zugang zu BiPRO-Services
- www.easy-login.de

---

## Nächste Schritte für unser Tool

### Priorität 1: BiPRO-Hub Anbindung prüfen
- [ ] Zugang zu biprohub.eu beantragen
- [ ] Hub-Authentifizierung implementieren
- [ ] Damit Zugriff auf 10+ VUs mit einer Anbindung

### Priorität 2: Weitere Direkt-Anbindungen
- [ ] Signal Iduna (großer Makler-VU)
- [ ] Gothaer (bekannt für gute BiPRO-Integration)
- [ ] Allianz (Marktführer)

### Priorität 3: TGIC-Zertifikat
- [ ] easy Login Zertifikat beantragen
- [ ] Für VUs die nur Zertifikats-Auth akzeptieren

---

## Kontakte

### BiPRO Service GmbH (Hub)
- Website: bipro-service.gmbh
- E-Mail: info@bipro-service.gmbh

### BiPRO e.V. (Standards)
- Website: www.bipro.net
- E-Mail: fida@bipro.net

### easy Login (Zertifikate)
- Website: www.easy-login.de

---

## Änderungshistorie

| Datum | Änderung |
|-------|----------|
| 02.02.2026 | Initiale Erstellung |
| 02.02.2026 | Degenia als funktionierend markiert |
| 04.02.2026 | VEMA als funktionierend markiert |
| 04.02.2026 | VU-spezifisches Verhalten dokumentiert (KRITISCH!) |
| 04.02.2026 | Design-Prinzip: Änderungen pro VU isoliert |
