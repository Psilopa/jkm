# APIKEY - yksinkertaisin, mutta heikoin varmistustapa
[https://console.cloud.google.com/agent-platform/studio/settings/api-key]
Luo koodi, tallenna se tiedostoon, ja kerro osoite ohjelmalle asetustiedoston kautta.

# Google Cloud OAUTH2 googlen työkaluja käyttäen
##Asenna Google Cloud SDK
Asenna Google Cloud SDK: https://docs.cloud.google.com/sdk/docs/install-sdk. 

[GCloud-project-id] = Laskutettavan Google Cloud-projektin nimi

##GCloud: Googlen 
Autentikoi terminaalissa komennoilla:

- ```gcloud auth init```
Older gloud versions may need a separate
- ```gcloud auth application-default login```
- ```gcloud auth application-default set-quota-project [GCloud-project-id]```

## Asetustiedosto (setup/...toml)
```auth_type = "CLOUD_OAUTH" ```

CLOUD_OAUTH tarvitsee lisätiedot JKM_GOOGLE_PROJECT_ID ja JKM_GOOGLE_LOCATION. Kts. TOML-tiedosto. 

# Google Cloud OAUTH2 ilman gcloud-ohjelmaa
- Avaa laskutusprojektin konsoli ([https://console.cloud.google.com/welcome?hl=en])
- Tarkasta, että projektissa on aktivoituna APIt Agent Platform API  (aiplatform.googleapis.com) ja Gemini API (generativelanguage.googleapis.com).
- Lisää jkm OAuth 2.0 Client:ksi ([https://console.cloud.google.com/auth/clients])
-- Tärkeää: ota talteen client_secret-data, joka tulee näkyviin VAIN KERRAN käytöllä Create-napin painamisen jälkeen. Tarjolla pitäisi olla mahdollisuus tallentaa suoraan json-tiedostoon. Tallenna se tiedostoon  (esim. jkm_secret_token.json). 
- Lisää jkm-Clientin käyttäjäksi/Audience operaattorit google-emailien perusteella ([https://console.cloud.google.com/auth/audience])

## Asetustiedosto
```auth_type = "LOCAL_OAUTH" ```

CLOUD_OAUTH tarvitsee lisätiedot JKM_GOOGLE_CLIENT_SECRET_JSON, JKM_GOOGLE_PROJECT_ID ja JKM_GOOGLE_LOCATION. Kts. TOML-tiedosto. 
