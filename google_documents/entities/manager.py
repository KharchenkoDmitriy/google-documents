# Google account scopes
import json
import os
import re

import googleapiclient
from googleapiclient import discovery
from oauth2client.service_account import ServiceAccountCredentials

from google_documents.entities.from_itemable import FromItemable

SCOPES = [
    'https://www.googleapis.com/auth/drive'  # Google Drive full access
]


class GoogleDriveDocumentManager:
    def __init__(self, file_cls: type(FromItemable)):
        self.file_cls = file_cls

    # By default file name is getting from `GOOGLE_DOCUMENT_SERVICE_JSON` enviroment variable
    default_service_account_file = os.environ.get("GOOGLE_DOCUMENT_SERVICE_JSON")

    # You can use custom file name, specifying it using(...) method
    custom_service_account_file = None

    resource_name = 'drive'
    version = 3

    def using(self, service_account_file):
        if not os.path.isfile(service_account_file):
            raise ValueError(f"`{service_account_file}` is not a file")
        self.custom_service_account_file = service_account_file
        return self

    @classmethod
    def get_service_from_credentials(cls, credentials):
        return discovery.build(cls.resource_name, f'v{cls.version}', credentials=credentials, cache_discovery=False)

    @classmethod
    def _get_service_from_service_account_file(cls, service_account_file):
        assert service_account_file, "Google Documents Service account file not found. " \
                                     "You should specify it via google_service_account_file or " \
                                     "in $GOOGLE_DOCUMENT_SERVICE_JSON " \
                                     "environment variable."

        credentials = ServiceAccountCredentials.from_json_keyfile_name(service_account_file, scopes=SCOPES)
        return cls.get_service_from_credentials(credentials)

    @classmethod
    def get_default_api_service(cls):
        return cls._get_service_from_service_account_file(cls.default_service_account_file)

    @property
    def _service_account_file(self):
        return self.custom_service_account_file or self.default_service_account_file

    def _get_api_service(self):
        return self._get_service_from_service_account_file(self._service_account_file)

    @property
    def service_account_credentials(self):
        return json.loads(open(self._service_account_file).read())

    def _get_item(self, id):
        return self._get_api_service().files().get(
                fileId=id).execute()

    def get(self, id):
        try:
            item = self._get_item(id)

            file_obj = self.file_cls.from_item(item)
            file_obj.set_api_service(self._get_api_service())
            return file_obj
        except googleapiclient.errors.HttpError:
            return None

    @staticmethod
    def _get_filter_folder_query(folder):
        return f"'{folder.id}' in parents"

    def filter(self, **kwargs):
        """
        Filters files according to passed parameters
        """
        special_query_getters = {
            "folder": self._get_filter_folder_query
        }

        # Add mime type to search exactly files of the respective type
        # (Search only documents when we're calling GoogleDocument.objects.filter(...)
        if self.file_cls.mime_type:
            kwargs['mime_type'] = self.file_cls.mime_type

        # Getting format query
        params_queries = []
        for param, value in kwargs.items():
            # Replace pythonic parameters like 'some_cool_parameter'
            # To google parameter like 'someCoolParameter'
            param_camel_case = re.sub('_[a-z]', lambda p: p.group(0)[-1].upper(), param)

            # Getting search query for every parameter
            if param in special_query_getters:
                params_queries.append(
                    special_query_getters[param](value)
                )
            elif type(value) == bool:
                params_queries.append(
                    f"{param_camel_case} = {value}"
                )
            else:
                params_queries.append(
                    f"{param_camel_case} contains '{value}'"
                )

        # Getting total query
        q = ' and '.join(params_queries)

        response = self._get_api_service().files().list(
            q=q,
            spaces='drive',
            fields='files(id, name, mimeType, parents)').execute()

        files_items = response.get('files', [])

        result = []
        for file_item in files_items:
            result.append(self.file_cls.from_item(file_item))
        return result


class GoogleDriveSpreadsheetManager(GoogleDriveDocumentManager):
    resource_name = 'sheets'
    version = 4