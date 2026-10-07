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

##Asetustiedosto
Tarkasta seuraavat arvot:
google_location = global
google_project_id = [GCloud-project-id]

# Google Cloud OAUTH2 ilman gcloud-ohjelmaa


TODO