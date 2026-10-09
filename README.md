# eToll România (TollRo / Rovinietă) pentru Home Assistant

Integrare neoficială care citește datele din contul tău de pe [etoll.ro](https://etoll.ro), noul portal CNAIR pentru rovinietă și TollRo, operațional din 1 octombrie 2026.

## Ce entități creează

**Pentru fiecare vehicul din cont** (un dispozitiv pentru fiecare număr de înmatriculare):

| Entitate | Tip | Detalii |
|---|---|---|
| Expirare rovinietă | `sensor` (timestamp) | Atribute: serie șasiu (VIN), categorie, normă Euro, masă maximă autorizată, sursă |
| Zile rămase rovinietă | `sensor` (zile) | 0 când a expirat |
| Rovinietă valabilă | `binary_sensor` | `on` cât timp rovinieta e valabilă |
| Serie șasiu (VIN) | `sensor` (diagnostic) | Apare și ca număr de serie pe pagina dispozitivului |

**Pentru cont:**

| Entitate | Tip |
|---|---|
| Sold credite TollRo | `sensor` (RON), suma creditelor PEAJ active |
| Notificări | `sensor` |
| Servicii active | `sensor`, cu defalcare pe tipuri în atribute |
| Notificare | `event`: se declanșează la fiecare notificare nouă din cont |
| Expirări | `calendar`: ziua expirării fiecărei roviniete + mentenanțele anunțate |

**Pentru platforma etoll.ro** (pagina publică de status):

| Entitate | Tip |
|---|---|
| Stare platformă | `sensor`: funcțional / probleme de performanță / întrerupere parțială / întrerupere majoră / în mentenanță; atribute cu fiecare componentă, incidentul curent și următoarea mentenanță |
| Problemă platformă | `binary_sensor` (problem): `on` la incident activ, componentă degradată sau mentenanță în curs |

### Evenimentul `etoll_ro_notification`
La fiecare notificare nouă se trimite și un eveniment pe magistrala HA, cu `type` (de ex. `VIGNETTE_WILL_EXPIRE`, `LOW_BALANCE`), `title`, `message`, `created`, `plate_number`. Notificările existente la pornirea HA nu sunt retrimise.

```yaml
triggers:
  - trigger: event
    event_type: etoll_ro_notification
actions:
  - action: notify.notify
    data:
      title: "eToll: {{ trigger.event.data.title }}"
      message: "{{ trigger.event.data.message }}"
```

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
- Endpoint-uri folosite (doar citire): `/api/profiles`, `/api/vehicles`, `/api/tolls?status=ACTIVE`, `/api/notifications`, `/api/notifications/summary`, plus pagina publică de status `/status/api/{components,incidents,schedules}`.
- Verificarea publică a rovinietei (cu CAPTCHA) **nu** este folosită.

## Depanare
Adaugă în `configuration.yaml`:
```yaml
logger:
  logs:
    custom_components.etoll_ro: debug
```
Diagnosticele (*⋮ → Descarcă diagnostice*) ascund e-mailul, parola, numerele de înmatriculare, seriile de șasiu și ID-urile.

## Limitări
- API-ul portalului nu e public și se poate schimba fără anunț.
- Soldul TollRo se calculează din serviciile active de tip credit (`PEAJ`). Câmpul exact se va confirma pe un cont care are credite.
- Integrarea nu este afiliată cu CNAIR.
