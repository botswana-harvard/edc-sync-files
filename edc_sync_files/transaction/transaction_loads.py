import os
import shutil

from os.path import join

from django.apps import apps as django_apps
from django.core import serializers
from django.core.files import File
from django.db.models import Q

from edc_sync.consumer import Consumer
from edc_sync.models import IncomingTransaction

from ..models import UploadTransactionFile
from .transaction_messages import transaction_messages


class TransactionLoadsPathError(Exception):
    pass


class TransactionLoadsDuplicateError(Exception):
    pass


class TransactionLoadsSequenceError(Exception):
    pass


class TransactionLoads:
    """Uploads transaction file in the server, creates incoming transaction and
       play incoming transaction and archive transaction file.
    """

    def __init__(self, path):
        self._outgoing_transactions = []
        self._valid = False
        self.is_consumed = False
        self.is_uploaded = False
        self.is_usb = False
        self.tx_pks = []
        self.upload_transaction_file = None
        self.file_object = None
        if not os.path.exists(path):
            raise TransactionLoadsPathError(f'Invalid path. Got {path}')
        self.filename = os.path.basename(path)
        try:
            UploadTransactionFile.objects.get(file_name=self.filename)
        except UploadTransactionFile.DoesNotExist:
            with open(path) as f:
                self.file_object = f
                if self.upload_file():
                    self.archive_file()
        else:
            self.is_uploaded = True
            print(f'File {self.filename} already uploaded.')
#             raise TransactionLoadsDuplicateError(
#                 f'File {self.filename} already uploaded.')

    def upload_file(self):
        try:
            UploadTransactionFile.objects.create(
                transaction_file=File(self.file_object),
                file_name=self.filename,
                batch_id=self.outgoing_transactions[0].batch_id,
                producer=self.outgoing_transactions[0].producer)
            self.incoming_transactions
        except IndexError as e:
            #             raise IndexError('Got {}'.format(str(e)))
            print(f"An error occurred. Got {e}")
        except ValueError as e:
            print(f"An error occurred. Got {e}")
        else:
            print("Applying transactions for {}".format(self.filename))
            self.is_consumed = Consumer(
                transactions=self.pending_tx_pks).consume()
            return True

    @property
    def outgoing_transactions(self):
        """Returns a list of deserialized outgoing transactions.
        """
        if not self._outgoing_transactions:
            try:
                json_txt = self.file_object.read()
                deserialized_object = serializers.deserialize(
                    "json", json_txt, ensure_ascii=True, use_natural_foreign_keys=True,
                    use_natural_primary_keys=False)
                for _, obj in enumerate(deserialized_object):
                    self.tx_pks.append(obj.object.tx_pk)
                    self._outgoing_transactions.append(obj.object)
                self.verify_sequence()
            except AttributeError as e:
                print(f'Error occurred. Got {e}')
        return self._outgoing_transactions

    @property
    def incoming_transactions(self):
        """ Creates incoming transactions from a list of deserialized
        outgoing transactions.
        """
        incoming_transactions = []
        for outgoing_transaction in self.outgoing_transactions:
            try:
                IncomingTransaction.objects.get(pk=outgoing_transaction.pk)
            except IncomingTransaction.DoesNotExist:
                data = outgoing_transaction.__dict__
                del data['using']
                del data['is_consumed_middleman']
                del data['is_consumed_server']
                del data['_state']
                incoming_transactions.append(
                    IncomingTransaction.objects.create(**data))
        return incoming_transactions

    def verify_sequence(self):
        """ Check order of transaction file batch seq.
        """
        new = self.outgoing_transactions[0].prev_batch_id == self.outgoing_transactions[0].batch_id
        exists = UploadTransactionFile.objects.filter(
            batch_id=self.outgoing_transactions[0].prev_batch_id).exists()
        if new or exists:
            return True
        else:
            return False
            # raise TransactionLoadsSequenceError(f'Invalid sequence for {self.filename}')

    def archive_file(self):
        edc_sync_file_app = django_apps.get_app_config('edc_sync_files')
        try:
            if self.is_usb:
                source_filename = join(
                    edc_sync_file_app.usb_incoming_folder, self.filename)
            else:
                source_filename = join(
                    edc_sync_file_app.destination_folder, self.filename)

            if os.path.exists(source_filename):
                shutil.move(
                    source_filename, edc_sync_file_app.archive_folder)  # archive the file
                print("File {} archived successfully into {}.".format(
                    self.filename, edc_sync_file_app.archive_folder))
                self.is_uploaded = False
                self.archived = True
            else:
                print("File {} does exists to be archived.".format(self.filename))
        except FileNotFoundError as e:
            transaction_messages.add_message(
                'error', 'Make sure archive dir exists in media/transactions/archive Got {}'.format(str(e)))
        except Exception as e:
            print(str(e))

    @property
    def pending_tx_pks(self):
        qs = IncomingTransaction.objects.values('tx_pk').filter(
            Q(is_consumed=True) | Q(is_ignored=True),
            batch_id=self.outgoing_transactions[0].prev_batch_id)
        consumed_tx_pks = [obj.get('tx_pk') for obj in qs]
        return [pk for pk in self.tx_pks if pk not in consumed_tx_pks]