# eToll România (TollRo / Rovinietă) pentru Home Assistant

Integrare neoficială care citește datele din contul tău de pe [etoll.ro](https://etoll.ro), noul portal CNAIR pentru rovinietă și TollRo, operațional din 1 octombrie 2026.

## Ce entități creează

**Pentru fiecare vehicul din cont** (un dispozitiv pentru fiecare număr de înmatriculare):

| Entitate | Tip | Detalii |
|---|---|---|
| Expirare rovinietă | `sensor` (timestamp) | Atribute: categorie, normă Euro, masă maximă autorizată, sursă |
| Zile rămase rovinietă | `sensor` (zile) | 0 când a expirat |
| Rovinietă valabilă | `binary_sensor` | `on` cât timp rovinieta e valabilă |

**Pentru cont:**

| Entitate | Tip |
|---|---|
| Sold credite TollRo | `sensor` (RON), suma creditelor PEAJ active |
| Notificări | `sensor` |
| Servicii active | `sensor`, cu defalcare pe tipuri în atribute |

Vehiculele adăugate ulterior în portal apar automat la următoarea actualizare.

## Instalare

### Prin HACS (repository personalizat)
1. În HACS → ⋮ → *Custom repositories*, adaugă `https://github.com/msuvar/ha-etoll-ro`, cu tipul **Integration**.
2. Caută **eToll România** în HACS.
3. Instalează **eToll România** și repornește Home Assistant.

### Manual
Copiază `custom_components/etoll_ro` în folderul `config/custom_components/` din Home Assistant, apoi repornește.

## Configurare
*Setări → Dispozitive și servicii → Adaugă integrare → eToll România*, apoi completează e-mailul și parola contului etoll.ro.

> Nu merge autentificarea prin Google, ROeID, eIDAS sau passkey. Dacă intri în portal doar pe una dintre aceste căi, setează mai întâi o parolă din „Ai uitat parola?”.

În *Opțiuni* poți schimba intervalul de actualizare: implicit 30 de minute, minim 10.

## Exemplu de automatizare
```yaml
alias: Rovinieta expiră curând
triggers:
  - trigger: numeric_state
    entity_id: sensor.b123abc_zile_ramase_rovinieta
    below: 8
actions:
  - action: notify.notify
    data:
      message: "Rovinieta pentru B123ABC expiră în {{ states('sensor.b123abc_zile_ramase_rovinieta') }} zile."
```

## Cum funcționează
- Autentificarea folosește același flux ca portalul web: Keycloak `sso.etoll.ro`, realm `external`, client `ddcm-authz-client`, cod de autorizare + PKCE. Token-ul se reîmprospătează automat, iar dacă a expirat integrarea se autentifică din nou.
- Endpoint-uri folosite (doar citire): `/api/profiles`, `/api/vehicles`, `/api/tolls?status=ACTIVE`, `/api/notifications/summary`.
- Verificarea publică a rovinietei (cu CAPTCHA) **nu** este folosită.

## Depanare
Adaugă în `configuration.yaml`:
```yaml
logger:
  logs:
    custom_components.etoll_ro: debug
```
Diagnosticele (*⋮ → Descarcă diagnostice*) ascund e-mailul, parola, numerele de înmatriculare și ID-urile.

## Limitări
- API-ul portalului nu e public și se poate schimba fără anunț.
- Soldul TollRo se calculează din serviciile active de tip credit (`PEAJ`). Câmpul exact se va confirma pe un cont care are credite.
- Integrarea nu este afiliată cu CNAIR.
