
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import time
import unittest

from baseplate.events import EventQueue
from baseplate.experiments import Experiments
from baseplate.features import Content, User
from baseplate.file_watcher import FileWatcher, WatchedFileNotAvailableError

from ... import mock

THIRTY_DAYS_SEC = 60 * 60 * 24 * 30


class TestExperiments(unittest.TestCase):

    def setUp(self):
        super(TestExperiments, self).setUp()
        self.event_queue = mock.Mock(spec=EventQueue)
        self.mock_filewatcher = mock.Mock(spec=FileWatcher)
        self.user = User(name="gary", id="t2_1", created=int(time.time()))

    def test_that_we_only_send_bucketing_event_once(self):
        self.mock_filewatcher.get_data.return_value = {
            "test": {
                "id": "1",
                "name": "test",
                "owner": "test",
                "type": "legacy",
                "expires": int(time.time()) + THIRTY_DAYS_SEC,
                "experiment": {
                    "id": "1",
                    "name": "test",
                    "variants": {
                        "active": 10,
                        "control_1": 10,
                        "control_2": 10,
                    }
                }
            }
        }
        experiments = Experiments(self.mock_filewatcher, self.event_queue)

        with mock.patch(
            "baseplate.experiments.providers.legacy.LegacyExperiment.variant",
            return_value="active",
        ):
            self.assertEqual(self.event_queue.put.call_count, 0)
            experiments.variant("test", user_id=self.user.id)
            self.assertEqual(self.event_queue.put.call_count, 1)
            experiments.variant("test", user_id=self.user.id)
            self.assertEqual(self.event_queue.put.call_count, 1)

    def test_that_bucketing_events_not_sent_if_no_variant(self):
        self.mock_filewatcher.get_data.return_value = {
            "test": {
                "id": "1",
                "name": "test",
                "owner": "test",
                "type": "legacy",
                "expires": int(time.time()) + THIRTY_DAYS_SEC,
                "experiment": {
                    "id": "1",
                    "name": "test",
                    "variants": {
                        "active": 10,
                        "control_1": 10,
                        "control_2": 10,
                    }
                }
            }
        }
        experiments = Experiments(self.mock_filewatcher, self.event_queue)

        with mock.patch(
            "baseplate.experiments.providers.legacy.LegacyExperiment.variant",
            return_value=None,
        ):
            self.assertEqual(self.event_queue.put.call_count, 0)
            experiments.variant("test", user_id=self.user.id)
            self.assertEqual(self.event_queue.put.call_count, 0)
            experiments.variant("test", user_id=self.user.id)
            self.assertEqual(self.event_queue.put.call_count, 0)

    def test_that_bucketing_events_not_sent_if_experiment_disables(self):
        self.mock_filewatcher.get_data.return_value = {
            "test": {
                "id": "1",
                "name": "test",
                "owner": "test",
                "type": "legacy",
                "expires": int(time.time()) + THIRTY_DAYS_SEC,
                "experiment": {
                    "id": "1",
                    "name": "test",
                    "variants": {
                        "active": 10,
                        "control_1": 10,
                        "control_2": 10,
                    }
                }
            }
        }
        experiments = Experiments(self.mock_filewatcher, self.event_queue)

        with mock.patch(
            "baseplate.experiments.providers.legacy.LegacyExperiment.variant",
            return_value="active",
        ), mock.patch(
            "baseplate.experiments.providers.legacy.LegacyExperiment.should_log_bucketing",
            return_value=False,
        ):
            self.assertEqual(self.event_queue.put.call_count, 0)
            experiments.variant("test", user_id=self.user.id)
            self.assertEqual(self.event_queue.put.call_count, 0)
            experiments.variant("test", user_id=self.user.id)
            self.assertEqual(self.event_queue.put.call_count, 0)

    def test_that_bucketing_events_not_sent_if_cant_load_config(self):
        self.mock_filewatcher.get_data.side_effect = WatchedFileNotAvailableError("path", None)  # noqa
        experiments = Experiments(self.mock_filewatcher, self.event_queue)
        self.assertEqual(self.event_queue.put.call_count, 0)
        experiments.variant("test", user_id=self.user.id)
        self.assertEqual(self.event_queue.put.call_count, 0)
        experiments.variant("test", user_id=self.user.id)
        self.assertEqual(self.event_queue.put.call_count, 0)

    def test_that_bucketing_events_not_sent_if_cant_parse_config(self):
        self.mock_filewatcher.get_data.side_effect = TypeError()
        experiments = Experiments(self.mock_filewatcher, self.event_queue)
        self.assertEqual(self.event_queue.put.call_count, 0)
        experiments.variant("test", user_id=self.user.id)
        self.assertEqual(self.event_queue.put.call_count, 0)
        experiments.variant("test", user_id=self.user.id)
        self.assertEqual(self.event_queue.put.call_count, 0)

    def test_that_bucketing_events_not_sent_if_cant_find_experiment(self):
        self.mock_filewatcher.get_data.return_value = {
            "other_test": {
                "id": "1",
                "name": "test",
                "owner": "test",
                "type": "legacy",
                "expires": int(time.time()) + THIRTY_DAYS_SEC,
                "experiment": {
                    "id": "1",
                    "name": "test",
                    "variants": {
                        "active": 10,
                        "control_1": 10,
                        "control_2": 10,
                    }
                }
            }
        }
        experiments = Experiments(self.mock_filewatcher, self.event_queue)
        self.assertEqual(self.event_queue.put.call_count, 0)
        experiments.variant("test", user_id=self.user.id)
        self.assertEqual(self.event_queue.put.call_count, 0)
        experiments.variant("test", user_id=self.user.id)
        self.assertEqual(self.event_queue.put.call_count, 0)
