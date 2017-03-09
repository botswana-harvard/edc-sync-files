from edc_base.utils import get_utcnow
from django.apps import apps as django_apps

from .file_transfer import FileTransfer


class TransactionFileManager(object):
    """Send files to the community server or central server.
    """

    def __init__(self, file_transfer=None, filename=None):
        self.file_transfer = file_transfer or FileTransfer()
        self.filename = filename
        self.approval_code = None

    def send_files(self):
        sent = self.file_transfer.copy_files(self.filename)
        archived = False
        if sent:
            archived = self.file_transfer.archive(self.filename)
        return (sent, archived)

    @property
    def file_transfer_progress(self):
        return self.file_transfer.file_connector.progress_status

    @property
    def device_id(self):
        app_config = django_apps.get_app_config('edc_device')
        return app_config.device_id

    def approve_transfer_files(self, files):
        approval_code = '{}{}'.format(
            self.device_id, str(get_utcnow().strftime("%Y%m%d%H%M")))
        for filename in files:
            self.file_transfer.approve_sent_file(filename, approval_code)
        return True

    def is_server_available(self):
        return self.file_transfer.file_connector.connected()
