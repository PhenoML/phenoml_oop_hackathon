import requests
import os
from typing import Dict, List, Any, Optional, Literal
from google.adk.agents import Agent
from datetime import datetime
import json

# Define all FHIR profiles with their corresponding resource types
FHIR_PROFILES = {
    "appointment": "Appointment",
    "condition-encounter-diagnosis": "Condition",
    "medicationrequest": "MedicationRequest",
    "careplan": "CarePlan",
    "condition-problems-health-concerns": "Condition",
    "coverage": "Coverage",
    "encounter": "Encounter",
    "invoice": "Invoice",
    "observation-clinical-result": "Observation",
    "observation-lab": "Observation",
    "patient": "Patient",
    "procedure": "Procedure",
    "questionnaire": "Questionnaire",
    "questionnaireresponse": "QuestionnaireResponse",
    "simple-observation": "Observation",
    "schedule": "Schedule",
    "slot": "Slot",
    "vital-signs": "Observation"
}

# Get the valid resource types from the profiles
FHIR_RESOURCE_TYPES = list(set(FHIR_PROFILES.values()))


def lang2fhir_and_create(
    natural_language_description: str, 
    profile: str,
    patient_id: Optional[str] = None,
    version: str = "R4",
    practitioner_id: Optional[str] = None,
    location_id: Optional[str] = None
) -> dict:
    """Converts natural language to a FHIR resource and directly creates it on the FHIR server.
    
    Args:
        natural_language_description (str): Natural language description of the resource to create.
        patient_id (str, optional): The patient ID to associate this resource with.
        resource_type (str): The specific FHIR profile to use. 
            Must be one of: appointment, condition-encounter-diagnosis, medicationrequest, careplan, 
            condition-problems-health-concerns, coverage, encounter, observation-clinical-result, 
            observation-lab, patient, procedure, questionnaire, questionnaireresponse, 
            simple-observation, schedule, slot, vital-signs.
            Select the most appropriate profile based on the description.
        version (str, optional): FHIR version to use. Defaults to "R4".
        practitioner_id (str, optional): The practitioner ID to associate with this resource. Required for appointments.
        location_id (str, optional): The location ID to associate with this resource. Required for appointments on Canvas FHIR servers.
        
    Returns:
        dict: Creation result with status and resource data or error message.
    """
    try:
        # Get tokens from environment variables
        phenoml_token = os.environ.get("PHENOML_TOKEN")
        medplum_token = os.environ.get("MEDPLUM_TOKEN")
        canvas_token = os.environ.get("CANVAS_TOKEN")
        canvas_instance_identifier = os.environ.get("CANVAS_INSTANCE_IDENTIFIER")
        
        if not phenoml_token:
            return {
                "status": "error",
                "error_message": "PHENOML_TOKEN environment variable not set"
            }
            
        if (not medplum_token and not canvas_token) or (medplum_token and canvas_token):
            return {
                "status": "error",
                "error_message": "Exactly one of MEDPLUM_TOKEN or CANVAS_TOKEN environment variable must be set"
            }
            
        # Set FHIR server URL
        if canvas_token and not medplum_token:
            fhir_server_url = f"https://fumage-{canvas_instance_identifier}.canvasmedical.com"
            fhir_access_token = canvas_token
        if medplum_token and not canvas_token:
            base_url = os.environ.get("MEDPLUM_BASE_URL")
            if not base_url:
                # if no base_url is provided, use the default api.medplum.com
                base_url = "https://api.medplum.com"
            fhir_server_url = f"{base_url}/fhir/R4"
            fhir_access_token = medplum_token
        
        # Validate resource type (profile)
        if profile not in FHIR_PROFILES:
            return {
                "status": "error",
                "error_message": f"Invalid profile: {profile}. Valid profiles are: {', '.join(FHIR_PROFILES.keys())}"
            }
        
        # Get the base FHIR resource type for this profile
        base_resource_type = FHIR_PROFILES.get(profile)
        
        # Step 1: Convert natural language to FHIR using lang2fhir
        lang2fhir_url = "https://experiment.app.pheno.ml/lang2fhir/create"
        lang2fhir_payload = {
            "version": version,
            "resource": profile,
            "text": natural_language_description
        }
        
        lang2fhir_headers = {
            "Authorization": f"Bearer {phenoml_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Call lang2fhir API to get FHIR resource
        lang2fhir_response = requests.post(lang2fhir_url, json=lang2fhir_payload, headers=lang2fhir_headers)
        
  
        lang2fhir_response.raise_for_status()
        
        fhir_resource = lang2fhir_response.json()
        
        # Step 2: Add patient reference to the resource if it's a clinical resource (not a Patient resource)
        if base_resource_type.lower() != "patient":
            # Handle Appointment resources differently - they use participant array
            if base_resource_type.lower() == "appointment":
                # Completely overwrite participants array with correctly formatted entries
                fhir_resource["participant"] = [
                    {
                        "actor": {"reference": f"Patient/{patient_id}"},
                        "status": "accepted"
                    }
                ]
                
                # Add practitioner if provided
                if practitioner_id:
                    fhir_resource["participant"].append({
                        "actor": {"reference": f"Practitioner/{practitioner_id}"},
                        "status": "accepted"
                    })
                
                # Ensure appointment has a status
                fhir_resource["status"] = "booked"
                
                # For Canvas Medical FHIR server, add supportingInformation with Location reference. this is a hack for the hackathon, adding support for Canvas FHIR profiles on lang2FHIR
                if canvas_token and not medplum_token:
                    
                    # Add location reference if provided
                    if location_id:
                        fhir_resource["supportingInformation"] = [
                            {"reference": f"Location/{location_id}"}
                        ]
                    else:
                        print("[WARNING] Canvas requires location_id for appointments")

            else:
                # Add subject reference for clinical resources
                fhir_resource["subject"] = {
                    "reference": f"Patient/{patient_id}"
                }
                
                # For specific resource types that use patient instead of subject
                if base_resource_type.lower() in ["encounter", "appointmentresponse", "appointmentrecurrence"]:
                    fhir_resource["patient"] = {
                        "reference": f"Patient/{patient_id}"
                    }
        
        # Step 3: Create the resource on the FHIR server
        fhir_headers = {
            "Authorization": f"Bearer {fhir_access_token}",
            "Content-Type": "application/json"
        }

        # Create the resource on the FHIR server
        fhir_url = f"{fhir_server_url}/{base_resource_type}"

        fhir_response = requests.post(fhir_url, json=fhir_resource, headers=fhir_headers)
        
        fhir_response.raise_for_status()
        
        # Handle 201 Created with empty body (common in Canvas)
        if fhir_response.status_code == 201 and not fhir_response.text.strip():
            created_resource = {
                "resourceType": base_resource_type,
                "status": "created"
            }
        else:
            created_resource = fhir_response.json()
        
        return {
            "status": fhir_response.status_code,
            "lang2fhir_result": fhir_resource,
            "fhir_resource": created_resource,
            "profile_used": profile,
            "base_resource_type": base_resource_type
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Failed to create resource: {str(e)}"
        }


def lang2fhir_and_search(
    natural_language_query: str
) -> dict:
    """Converts a natural language query to FHIR search parameters and performs the search in one operation.
    
    Args:
        natural_language_query (str): Natural language search query like "Find all patients with diabetes".
        
    Returns:
        dict: Search result with status and search results or error message.
    """
    try:
        
        # Get tokens from environment variables
        phenoml_token = os.environ.get("PHENOML_TOKEN")
        medplum_token = os.environ.get("MEDPLUM_TOKEN")
        canvas_token = os.environ.get("CANVAS_TOKEN")
        canvas_instance_identifier = os.environ.get("CANVAS_INSTANCE_IDENTIFIER")

        if not phenoml_token:
            return {
                "status": "error",
                "error_message": "PHENOML_TOKEN environment variable not set"
            }
            
        if (not medplum_token and not canvas_token) or (medplum_token and canvas_token):
            return {
                "status": "error",
                "error_message": "Exactly one of MEDPLUM_TOKEN or CANVAS_TOKEN environment variable must be set"
            }
            
        # Set FHIR server URL
        if canvas_token and not medplum_token:
            fhir_server_url = f"https://fumage-{canvas_instance_identifier}.canvasmedical.com"
            fhir_access_token = canvas_token
        if medplum_token and not canvas_token:
            base_url = os.environ.get("MEDPLUM_BASE_URL")
            if not base_url:
                # if no base_url is provided, use the default api.medplum.com
                base_url = "https://api.medplum.com"
            fhir_server_url = f"{base_url}/fhir/R4"
            fhir_access_token = medplum_token


        # Step 1: Convert natural language to FHIR search parameters using lang2fhir
        lang2fhir_url = "https://experiment.app.pheno.ml/lang2fhir/search"
        lang2fhir_payload = {
            "text": natural_language_query
        }

        lang2fhir_headers = {
            "Authorization": f"Bearer {phenoml_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Call lang2fhir API to get FHIR search parameters
        lang2fhir_response = requests.post(lang2fhir_url, json=lang2fhir_payload, headers=lang2fhir_headers)
        
        lang2fhir_response.raise_for_status()
        
        search_params = lang2fhir_response.json()
        
        # Extract resource type and search parameters from lang2fhir response
        detected_resource_type = search_params.get("resourceType")
        search_params_str = search_params.get("searchParams", "")
        
        # remove this debug line if you want! it's helping to get a little bit of chain of thought
        print(f"[DEBUG] Search for: {detected_resource_type} with params: {search_params_str}")
        
        # Build search URL
        fhir_url = f"{fhir_server_url}/{detected_resource_type}"
        
        # Add search parameters with proper reference handling for FHIR
        if search_params_str:
            # Parse parameters
            parts = search_params_str.split('&')
            fixed_parts = []
            
            for part in parts:
                if '=' in part:
                    name, value = part.split('=', 1)
                    
                    if ('/' not in value and 
                        # Pattern match for UUIDs so we know it's a reference Id
                        ('-' in value or value.startswith('0') and len(value) > 20)):
                        
                        # Simple mapping of parameter names to resource types
                        param_to_resource = {
                            # Common reference parameters
                            'patient': 'Patient',
                            'subject': 'Patient',
                            'practitioner': 'Practitioner',
                            'actor': 'Practitioner',
                            'provider': 'Practitioner',
                            'schedule': 'Schedule',
                            'encounter': 'Encounter',
                            'organization': 'Organization',
                            'location': 'Location',
                            'slot': 'Slot',
                            'appointment': 'Appointment',
                        }
                        
                        # Try to determine resource type
                        resource_type = None
                        
                        # 1. Check if parameter name is in our mapping
                        if name in param_to_resource:
                            resource_type = param_to_resource[name]
                        
                        # 2. If parameter ends with 'Id', strip 'Id' and capitalize, backup to catch references
                        elif name.endswith('Id'):
                            resource_type = name[:-2].capitalize()
                        
                        # 3. Check if parameter matches a FHIR resource type (case-insensitive)
                        else:
                            # Try to find a matching resource type
                            for rt in FHIR_RESOURCE_TYPES:
                                if rt.lower() == name.lower():
                                    resource_type = rt
                                    break
                            
                        # If we identified a resource type, format as a proper reference
                        if resource_type:
                            fixed_parts.append(f"{name}={resource_type}/{value}")
                        else:
                            fixed_parts.append(part)
                    else:
                        fixed_parts.append(part)
                else:
                    fixed_parts.append(part)
            
            # Reconstruct the query string and add pagination, this is a hack for the hackathon lol, ideally you'd want to handle pagination properly
            search_params_str = '&'.join(fixed_parts)
            fhir_url = f"{fhir_url}?{search_params_str}&_count=250"
        else:
            # No search params, just add pagination
            fhir_url = f"{fhir_url}?_count=250"
        
                
        fhir_headers = {
            "Authorization": f"Bearer {fhir_access_token}",
            "Content-Type": "application/json"
        }
        
        # Execute the search on the FHIR server
        fhir_response = requests.get(fhir_url, headers=fhir_headers)
        
        fhir_response.raise_for_status()
        
        search_results = fhir_response.json()
        
        return {
            "status": "success",
            "search_params": search_params,
            "search_results": search_results,
            "resource_type_used": detected_resource_type
        }
    except Exception as e:

        return {
            "status": "error",
            "error_message": f"Search failed: {str(e)}"
        }


def lang2fhir_document_upload(
    image_path: str,
    profile: str,
    patient_id: Optional[str] = None,
    version: str = "R4"
) -> dict:
    """Uploads an image file and converts it to a FHIR document.
    
    Args:
        image_path (str): Path to the image file to be uploaded.
        profile (str): The specific FHIR profile to use.
            Must be one of the profiles defined in FHIR_PROFILES.
        patient_id (str, optional): The patient ID to associate this document with.
            If provided, a subject reference will be added to the document.
        version (str, optional): FHIR version to use. Defaults to "R4".
        
    Returns:
        dict: Response from the document processing API with FHIR resource or error message.
    """
    try:
        import base64
        
        # Get token from environment variable
        phenoml_token = os.environ.get("PHENOML_TOKEN")
        
        if not phenoml_token:
            return {
                "status": "error",
                "error_message": "PHENOML_TOKEN environment variable not set"
            }
        
        # Validate profile
        if profile not in FHIR_PROFILES:
            return {
                "status": "error",
                "error_message": f"Invalid profile: {profile}. Valid profiles are: {', '.join(FHIR_PROFILES.keys())}"
            }
        
        # Get the base FHIR resource type for this profile
        base_resource_type = FHIR_PROFILES.get(profile)
            
        # Read and encode the image file
        with open(image_path, 'rb') as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
            
        # Determine the file type based on file extension
        file_extension = image_path.split('.')[-1].lower()
        file_type_mapping = {
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'pdf': 'application/pdf',
            'tiff': 'image/tiff',
            'tif': 'image/tiff'
        }
        
        file_type = file_type_mapping.get(file_extension, 'application/octet-stream')
        
        # Create payload for the document API
        payload = {
            "resource": profile,
            "fileType": file_type,
            "version": version,
            "content": encoded_image
        }
        
        # Set up request to lang2fhir document API
        document_url = "https://experiment.app.pheno.ml/lang2fhir/document"
        headers = {
            "Authorization": f"Bearer {phenoml_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Send request to process the document
        response = requests.post(document_url, json=payload, headers=headers)
        
        response.raise_for_status()
        
        fhir_resource = response.json()
        
        # Add patient reference to the resource if patient_id is provided
        if patient_id and base_resource_type.lower() != "patient":
            # Different resources may use different fields for patient references
            if base_resource_type.lower() in ["encounter", "appointmentresponse", "appointmentrecurrence"]:
                fhir_resource["patient"] = {
                    "reference": f"Patient/{patient_id}"
                }
            else:
                # Most resources use subject for patient reference
                fhir_resource["subject"] = {
                    "reference": f"Patient/{patient_id}"
                }
        
        return {
            "status": "success",
            "document_result": fhir_resource,
            "profile_used": profile,
            "base_resource_type": base_resource_type
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Document processing failed: {str(e)}"
        }


root_agent = Agent(
    name="phenoml_fhir_agent",
    model="gemini-2.0-flash",
    description=(
        "Agent to convert natural language to FHIR resources and queries using PhenoML lang2fhir API."
    ),
    instruction=(
        "You are a helpful agent who can create FHIR resources from natural language descriptions and "
        "search for FHIR resources using natural language queries through PhenoML's lang2fhir API. "
        "You can also perform direct FHIR operations on a FHIR server. "
        "Available FHIR profiles include: " +
        ", ".join(FHIR_PROFILES.keys()) + "\n\n"
        
        "CURRENT DATE: Today's date is " + 
        datetime.now().strftime("%Y-%m-%d") + ". Always use this as your reference point when "
        "handling relative dates like 'tomorrow' or 'next week'.\n\n"
        
        "IMPORTANT: When a user asks a question or makes a request, follow these steps:\n"
        "1. TRANSLATE the user's intent into relevant FHIR concepts\n"
        "2. DETERMINE which FHIR resources are needed (Patient, Appointment, Condition, etc.)\n"
        "3. DECIDE whether to search for existing resources or create new ones\n"
        "4. USE the appropriate tool:\n"
        "   - lang2fhir_and_search: When looking for clinical data or other resources\n"
        "   - lang2fhir_and_create: When creating new clinical data or resources\n\n"
        
        "CRITICAL PATIENT WORKFLOW: When a user mentions a patient by name (not ID):\n"
        "1. FIRST use lang2fhir_and_search to find the patient by name (e.g., 'Find patient John Smith')\n"
        "2. EXTRACT the patient ID from the search results\n"
        "3. THEN use that ID for any subsequent operations that require a patient_id\n\n"
        
        "APPOINTMENT WORKFLOW: When creating appointments that involve both patients and practitioners:\n"
        "1. FIRST use lang2fhir_and_search to find the patient by name\n"
        "2. ALSO use lang2fhir_and_search to find the practitioner by name\n"
        "3. EXTRACT both patient ID and practitioner ID from search results\n"
        "4. FIND the location for the appointment using one of these methods:\n"
        "   a. Find Schedule for the practitioner and extract its location reference\n"
        "   b. Search for locations associated with the practitioner\n"
        "   c. Or find any active location in the system\n"
        "   d. If you can't find a location, ask the user to provide one\n"
        "5. EXTRACT the location ID to use in the appointment creation\n"
        "6. When calling lang2fhir_and_create for an appointment, ALWAYS include:\n"
        "   a. patient_id parameter with the patient's ID\n"
        "   b. practitioner_id parameter with the practitioner's ID\n"
        "   c. location_id parameter with the location's ID\n"
        "7. Use natural language to describe the appointment clearly in the description\n"
        "8. The tool will automatically handle adding the location to supportingInformation for Canvas\n\n"
        
        "PROVIDER AVAILABILITY WORKFLOW: When checking if a provider is available:\n"
        "1. FIRST use lang2fhir_and_search to find the practitioner by name to get practitioner ID\n"
        "2. THEN use lang2fhir_and_search to find the practitioner's Schedule resource using practitioner ID\n"
        "3. EXTRACT the schedule identifier from the search results\n"
        "4. ALSO EXTRACT any location reference from the Schedule (this will be needed for appointment creation)\n"
        "5. FINALLY use lang2fhir_and_search with the schedule identifier to check available Slot resources\n"
        "6. FILTER OUT any slots with start times in the past (before today's date)\n"
        "   - IMPORTANT: Parse dates correctly by extracting YYYY-MM-DD from the slot start time\n"
        "   - COMPARE dates using datetime objects, not string comparison\n"
        "   - Today's date is " + datetime.now().strftime("%Y-%m-%d") + "\n"
        "   - If a slot date is EXACTLY " + datetime.now().strftime("%Y-%m-%d") + ", INCLUDE it\n"
        "   - ALWAYS INCLUDE slots from today or future dates\n"
        "7. When asked about 'next week' or other relative timeframes, ONLY show slots within that specific time period\n"
        "8. SORT available slots by date and time to present them in chronological order\n"
        "9. REPORT back available times based on the filtered Slot resources or indicate if no slots are available\n"
        "10. SAVE the location information from the Schedule for use in future appointment creation\n"
        "11. This ensures accurate scheduling information and collects the location needed for appointment creation\n\n"
        
        "IMPORTANT SAFETY CHECK: When multiple patients match a name search:\n"
        "1. PRESENT all matching patients with their identifiers (ID, DOB, etc.)\n"
        "2. ASK the user to confirm which specific patient they meant\n"
        "3. ONLY proceed with the confirmed patient ID\n"
        "4. This prevents accidentally associating clinical data with the wrong patient\n\n"
        
        "For example, if user says 'Record that Bob has diabetes':\n"
        "  - First: Use lang2fhir_and_search with 'Find patient Bob' to get Bob's ID\n"
        "  - Then: Use lang2fhir_and_create with the correct patient ID to create the condition\n\n"
        
        "For example, if user says 'Book an appointment for John with Dr. Smith tomorrow':\n"
        "  - First: Use lang2fhir_and_search with 'Find patient John' to get John's ID\n"
        "  - Next: Use lang2fhir_and_search with 'Find practitioner Dr. Smith' to get Dr. Smith's ID\n"
        "  - Next: Use lang2fhir_and_search with 'Find location for Dr. Smith' to get a location ID\n"
        "  - Finally: Use lang2fhir_and_create with:\n"
        "    * patient_id=John's ID\n"
        "    * practitioner_id=Dr. Smith's ID\n"
        "    * location_id=Location ID\n"
        "    * profile='appointment'\n"
        "    * description='Appointment for John with Dr. Smith tomorrow at 2 PM for check-up'\n\n"
        
        "For lang2fhir_and_create: When creating resources, select the most appropriate profile based on the description. "
        "For example:\n"
        "- For diagnoses made during visits: 'condition-encounter-diagnosis'\n"
        "- For medications and prescriptions: 'medicationrequest'\n"
        "- For care plans and treatment goals: 'careplan'\n"
        "- For ongoing health problems: 'condition-problems-health-concerns'\n"
        "- For appointments: 'appointment'\n"
        "- For lab results: 'observation-lab'\n"
        "- For patient information: 'patient'\n"
        "- For procedures performed: 'procedure'\n"
        "- For forms with questions: 'questionnaire'\n"
        "- For completed questionnaires: 'questionnaireresponse'\n"
        "- For basic measurements: 'simple-observation'\n"
        "- For vital signs like blood pressure: 'vital-signs'\n\n"
        
        "For lang2fhir_document_upload: When uploading documents or images for FHIR conversion:\n"
        "- Provide the full path to the image file\n"
        "- ALWAYS specify the profile you want to use (e.g., 'invoice', 'patient', etc.)\n"
        "- Optionally provide a patient_id to associate the document with a specific patient\n"
        "- If patient_id is provided, a subject reference will be automatically added\n"
        "- Valid profiles are the same as those used for lang2fhir_and_create\n"
        "- The function will automatically detect file type based on extension\n"
        "- Supported formats include PNG, JPEG, PDF, and TIFF\n"
        "- The document will be processed and converted to a FHIR resource\n\n"
        
        "Examples of translating user intent to FHIR actions:\n"
        "- 'Book an appointment for John with Dr. Smith tomorrow':\n"
        "   1) Find John's ID with lang2fhir_and_search\n" 
        "   2) Find Dr. Smith's ID with lang2fhir_and_search\n"
        "   3) Create appointment with both IDs and clear details about date, time, and purpose\n"
        "- 'What medications is Sarah taking?':\n"
        "   1) Find Sarah's ID with lang2fhir_and_search\n"
        "   2) Search for MedicationRequest resources with that ID\n"
        "- 'Record that Bob has diabetes':\n"
        "   1) Find Bob's ID with lang2fhir_and_search\n"
        "   2) Create condition with Bob's ID\n"
        "- 'When is my next appointment?':\n" 
        "   1) Find user's ID with lang2fhir_and_search\n"
        "   2) Search for Appointment resources with that ID\n\n"
        
        "- 'Upload this invoice from /path/to/invoice.png':\n"
        "   1) Use lang2fhir_document_upload with the provided file path\n"
        "   2) MUST specify the profile parameter (e.g., profile='invoice')\n"
        "   3) The document will be processed and converted to the appropriate FHIR resource\n\n"
        
        "- 'Upload this invoice from /path/to/invoice.png for patient John':\n"
        "   1) First use lang2fhir_and_search to find patient John and get their ID\n"
        "   2) Then use lang2fhir_document_upload with the file path, profile='invoice', and patient_id\n"
        "   3) The document will be processed and linked to the patient's record\n\n"
        
        "Always respond to the user's intent, not just explaining FHIR concepts."
    ),
    tools=[
        lang2fhir_and_create,
        lang2fhir_and_search,
        lang2fhir_document_upload,
    ],
)
