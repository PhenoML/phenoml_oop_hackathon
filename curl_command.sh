
curl --request POST \
  --url https://experiment.app.pheno.ml/lang2fhir/document \
  --header 'accept: application/json' \
  --header 'authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjb2xsZWN0aW9uSWQiOiJfcGJfdXNlcnNfYXV0aF8iLCJleHAiOjE3NDg3MTQ3OTYsImlkIjoidTc4bXF4aHBwZHd1dDZzIiwidHlwZSI6ImF1dGhSZWNvcmQifQ.HmXZ9x496EVN1HIEoJhiCVfuoQCauQWRtaaXhN5_zUo' \
  --header 'content-type: application/json' \
  --data @payload.json
