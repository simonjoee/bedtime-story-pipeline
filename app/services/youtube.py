import os
import logging
import google.oauth2.credentials
import google_auth_oauthlib.flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'

class YouTubeService:
    def __init__(self):
        self.client_secrets_file = os.getenv("CLIENT_SECRETS_FILE", "client_secrets.json")
        self.token_file = "data/youtube_token.json"
    
    def get_authenticated_service(self):
        flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
            self.client_secrets_file, SCOPES)
        
        if os.path.exists(self.token_file):
            credentials = google.oauth2.credentials.Credentials.from_authorized_user_file(
                self.token_file, SCOPES)
            if credentials and credentials.valid:
                return build(API_SERVICE_NAME, API_VERSION, credentials=credentials)
        
        credentials = flow.run_local_server(port=8080, prompt='consent')
        os.makedirs(os.path.dirname(self.token_file), exist_ok=True)
        with open(self.token_file, 'w') as f:
            f.write(credentials.to_json())
        
        return build(API_SERVICE_NAME, API_VERSION, credentials=credentials)
    
    def upload_video(self, video_path: str, title: str, description: str = "", tags: list = None) -> dict:
        try:
            youtube = self.get_authenticated_service()
            
            body = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'tags': tags or [],
                    'categoryId': '22'
                },
                'status': {
                    'privacyStatus': 'public',
                    'selfDeclaredMadeForKids': False
                }
            }
            
            media = MediaFileUpload(video_path, resumable=True)
            
            request = youtube.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )
            
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    logger.info(f"Upload {int(status * 100)}%")
            
            logger.info(f"Video uploaded: https://youtube.com/watch?v={response['id']}")
            return {
                'video_id': response['id'],
                'video_url': f"https://youtube.com/watch?v={response['id']}"
            }
            
        except HttpError as e:
            logger.error(f"YouTube upload error: {e}")
            raise Exception(f"上传失败: {e.resp.status}")
        except Exception as e:
            logger.error(f"YouTube upload error: {e}")
            raise

youtube_service = YouTubeService()
