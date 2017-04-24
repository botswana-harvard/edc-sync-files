import logging
import time

from django.utils import timezone

from watchdog.observers import Observer

from .transaction_file_event_handler import TransactionFileEventHandler


class ServerObserver:

    def start_observer(self):

        event_handler = TransactionFileEventHandler()
        observer = Observer()
        observer.schedule(event_handler, path=self.destination_folder)
        observer.start()
        logging.basicConfig(filename='logs/observer-error.log', level=logging.INFO)
        logger = logging.getLogger(__name__)
        try:
            records = {'time': timezone.now(), 'status': 'running'}
            logger.info('{}'.format(records))
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        except (OSError, IOError) as err:
            records = {'time': timezone.now(), 'status': '{}'.format(str(err))}
            logger.error('{}'.format(records))
            time.sleep(1)
            observer.stop()
            self.start_observer()
        observer.join()
