import base64
import json

# Read and encode the image file
with open('IMG_1802.png', 'rb') as image_file:
    encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

# Create the JSON payload
payload = {
    "resource": "invoice",
    "fileType": "image/png",
    "version": "R4",
    "content": encoded_string
}

# Write the payload to a JSON file
with open('payload.json', 'w') as json_file:
    json.dump(payload, json_file)

# Create the curl command that references the JSON file
curl_command = """
curl --request POST \\
  --url https://experiment.app.pheno.ml/lang2fhir/document \\
  --header 'accept: application/json' \\
  --header 'authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjb2xsZWN0aW9uSWQiOiJfcGJfdXNlcnNfYXV0aF8iLCJleHAiOjE3NDg3MTQ3OTYsImlkIjoidTc4bXF4aHBwZHd1dDZzIiwidHlwZSI6ImF1dGhSZWNvcmQifQ.HmXZ9x496EVN1HIEoJhiCVfuoQCauQWRtaaXhN5_zUo' \\
  --header 'content-type: application/json' \\
  --data @payload.json
"""

# Output the command to a file
with open('curl_command.sh', 'w') as file:
    file.write(curl_command)

print("JSON payload has been written to payload.json")
print("Curl command has been written to curl_command.sh")
print("You can run it with: sh curl_command.sh") 