import logging
import os
import atexit
import tempfile
import threading
import time
import requests
import queue
import pymongo

import ftrack_api
import ftrack_api.session
import ftrack_api.cache
import ftrack_api.operation
import ftrack_api._centralized_storage_scenario
import ftrack_api.event
from ftrack_api.logging import LazyLogMessage as L

from pype.ftrack.lib.custom_db_connector import DbConnector


class ProcessEventHub(ftrack_api.event.hub.EventHub):
    dbcon = DbConnector(
        mongo_url=os.environ["AVALON_MONGO"],
        database_name="pype"
    )
    table_name = "ftrack_events"
    is_table_created = False

    def __init__(self, *args, **kwargs):
        self.sock = kwargs.pop("sock")
        super(ProcessEventHub, self).__init__(*args, **kwargs)

    def prepare_dbcon(self):
        try:
            self.dbcon.install()
            if not self.is_table_created:
                self.dbcon.create_table(self.table_name, capped=False)
                self.dbcon.active_table = self.table_name
                self.is_table_created = True
        except pymongo.errors.AutoReconnect:
            sys.exit(0)

    def wait(self, duration=None):
        '''Wait for events and handle as they arrive.

        If *duration* is specified, then only process events until duration is
        reached. *duration* is in seconds though float values can be used for
        smaller values.

        '''
        started = time.time()
        self.prepare_dbcon()
        while True:
            try:
                event = self._event_queue.get(timeout=0.1)
            except queue.Empty:
                if not self.load_events():
                    time.sleep(0.5)
            else:
                try:
                    self._handle(event)
                    self.dbcon.update_one(
                        {"id": event["id"]},
                        {"$set": {"pype_data.is_processed": True}}
                    )
                except pymongo.errors.AutoReconnect:
                    sys.exit(0)
                # Additional special processing of events.
                if event['topic'] == 'ftrack.meta.disconnected':
                    break

            if duration is not None:
                if (time.time() - started) > duration:
                    break

    def load_events(self):
        not_processed_events = self.dbcon.find(
            {"pype_data.is_processed": False}
        ).sort(
            [("pype_data.stored", pymongo.ASCENDING)]
        )

        found = False
        for event_data in not_processed_events:
            new_event_data = {
                k: v for k, v in event_data.items()
                if k not in ["_id", "pype_data"]
            }
            try:
                event = ftrack_api.event.base.Event(**new_event_data)
            except Exception:
                self.logger.exception(L(
                    'Failed to convert payload into event: {0}',
                    event_data
                ))
                continue
            found = True
            self._event_queue.put(event)

        return found

    def _handle_packet(self, code, packet_identifier, path, data):
        '''Handle packet received from server.'''
        # if self.is_waiting:
        code_name = self._code_name_mapping[code]
        if code_name == "event":
            return
        if code_name == "heartbeat":
            self.sock.sendall(b"processor")
            return self._send_packet(self._code_name_mapping["heartbeat"])

        return super()._handle_packet(code, packet_identifier, path, data)


class ProcessSession(ftrack_api.session.Session):
    '''An isolated session for interaction with an ftrack server.'''
    def __init__(
        self, server_url=None, api_key=None, api_user=None, auto_populate=True,
        plugin_paths=None, cache=None, cache_key_maker=None,
        auto_connect_event_hub=None, schema_cache_path=None,
        plugin_arguments=None, sock=None
    ):
        super(ftrack_api.session.Session, self).__init__()
        self.logger = logging.getLogger(
            __name__ + '.' + self.__class__.__name__
        )
        self._closed = False

        if server_url is None:
            server_url = os.environ.get('FTRACK_SERVER')

        if not server_url:
            raise TypeError(
                'Required "server_url" not specified. Pass as argument or set '
                'in environment variable FTRACK_SERVER.'
            )

        self._server_url = server_url

        if api_key is None:
            api_key = os.environ.get(
                'FTRACK_API_KEY',
                # Backwards compatibility
                os.environ.get('FTRACK_APIKEY')
            )

        if not api_key:
            raise TypeError(
                'Required "api_key" not specified. Pass as argument or set in '
                'environment variable FTRACK_API_KEY.'
            )

        self._api_key = api_key

        if api_user is None:
            api_user = os.environ.get('FTRACK_API_USER')
            if not api_user:
                try:
                    api_user = getpass.getuser()
                except Exception:
                    pass

        if not api_user:
            raise TypeError(
                'Required "api_user" not specified. Pass as argument, set in '
                'environment variable FTRACK_API_USER or one of the standard '
                'environment variables used by Python\'s getpass module.'
            )

        self._api_user = api_user

        # Currently pending operations.
        self.recorded_operations = ftrack_api.operation.Operations()
        self.record_operations = True

        self.cache_key_maker = cache_key_maker
        if self.cache_key_maker is None:
            self.cache_key_maker = ftrack_api.cache.StringKeyMaker()

        # Enforce always having a memory cache at top level so that the same
        # in-memory instance is returned from session.
        self.cache = ftrack_api.cache.LayeredCache([
            ftrack_api.cache.MemoryCache()
        ])

        if cache is not None:
            if callable(cache):
                cache = cache(self)

            if cache is not None:
                self.cache.caches.append(cache)

        self._managed_request = None
        self._request = requests.Session()
        self._request.auth = ftrack_api.session.SessionAuthentication(
            self._api_key, self._api_user
        )

        self.auto_populate = auto_populate

        # Fetch server information and in doing so also check credentials.
        self._server_information = self._fetch_server_information()

        # Now check compatibility of server based on retrieved information.
        self.check_server_compatibility()

        # Construct event hub and load plugins.
        self._event_hub = ProcessEventHub(
            self._server_url,
            self._api_user,
            self._api_key,
            sock=sock
        )

        self._auto_connect_event_hub_thread = None
        if auto_connect_event_hub in (None, True):
            # Connect to event hub in background thread so as not to block main
            # session usage waiting for event hub connection.
            self._auto_connect_event_hub_thread = threading.Thread(
                target=self._event_hub.connect
            )
            self._auto_connect_event_hub_thread.daemon = True
            self._auto_connect_event_hub_thread.start()

        # To help with migration from auto_connect_event_hub default changing
        # from True to False.
        self._event_hub._deprecation_warning_auto_connect = (
            auto_connect_event_hub is None
        )

        # Register to auto-close session on exit.
        atexit.register(self.close)

        self._plugin_paths = plugin_paths
        if self._plugin_paths is None:
            self._plugin_paths = os.environ.get(
                'FTRACK_EVENT_PLUGIN_PATH', ''
            ).split(os.pathsep)

        self._discover_plugins(plugin_arguments=plugin_arguments)

        # TODO: Make schemas read-only and non-mutable (or at least without
        # rebuilding types)?
        if schema_cache_path is not False:
            if schema_cache_path is None:
                schema_cache_path = os.environ.get(
                    'FTRACK_API_SCHEMA_CACHE_PATH', tempfile.gettempdir()
                )

            schema_cache_path = os.path.join(
                schema_cache_path, 'ftrack_api_schema_cache.json'
            )

        self.schemas = self._load_schemas(schema_cache_path)
        self.types = self._build_entity_type_classes(self.schemas)

        ftrack_api._centralized_storage_scenario.register(self)

        self._configure_locations()
        self.event_hub.publish(
            ftrack_api.event.base.Event(
                topic='ftrack.api.session.ready',
                data=dict(
                    session=self
                )
            ),
            synchronous=True
        )
