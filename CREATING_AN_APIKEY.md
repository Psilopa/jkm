
Asenna Google Cloud SDK: https://docs.cloud.google.com/sdk/docs/install-sdk

Autentikoi terminaalissa komennoilla:
gcloud auth application-default login
gcloud auth application-default set-quota-project <ASK_MIKKO_HEIKKINEN>

Sitten mocodigissa kopioi .env.example tiedosto .env-tiedostoksi ja lisää siihen

GOOGLE_CLOUD_PROJECT=<ASK_MIKKO_HEIKKINEN>

