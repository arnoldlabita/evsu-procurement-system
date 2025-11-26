from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2 import service_account
import io
from django.conf import settings

def upload_file_to_drive(file, filename):
    SCOPES = ['https://www.googleapis.com/auth/drive.file']
    
    creds = service_account.Credentials.from_service_account_file(
        settings.GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )

    service = build('drive', 'v3', credentials=creds)

    file_metadata = {
        'name': filename,
        'parents': [settings.GOOGLE_DRIVE_FOLDER_ID]
    }

    media = MediaIoBaseUpload(file, mimetype=file.content_type, resumable=True)

    uploaded_file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink'
    ).execute()

    return uploaded_file.get("webViewLink")

def create_folder_in_drive(folder_name, parent_folder_id=None):
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_file(settings.GOOGLE_DRIVE_CREDENTIALS)
    service = build('drive', 'v3', credentials=creds)

    metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    if parent_folder_id:
        metadata['parents'] = [parent_folder_id]

    folder = service.files().create(body=metadata, fields='id').execute()
    return folder.get('id')


def upload_file_to_drive(file, folder_id=None):
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    from google.oauth2.service_account import Credentials
    import io

    creds = Credentials.from_service_account_file(settings.GOOGLE_DRIVE_CREDENTIALS)
    service = build('drive', 'v3', credentials=creds)

    file_metadata = {'name': file.name}
    if folder_id:
        file_metadata['parents'] = [folder_id]

    media = MediaIoBaseUpload(io.BytesIO(file.read()), mimetype=file.content_type)
    uploaded = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    return uploaded.get("id")
