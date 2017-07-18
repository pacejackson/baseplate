
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import time
import unittest

from baseplate.experiments.providers import experiment_from_config
from baseplate.experiments.providers.forced_variant import ForcedVariantExperiment

THIRTY_DAYS_SEC = 60 * 60 * 24 * 30


class TestForcedVariantExperiment(unittest.TestCase):

    def test_unknown_type_returns_null_experiment(self):
        cfg = {
            "id": "1",
            "name": "test",
            "owner": "test",
            "type": "unknown",
            "expires": int(time.time()) + THIRTY_DAYS_SEC,
            "experiment": {
                "id": "1",
                "name": "test",
                "variants": {
                    "control_1": 10,
                    "control_2": 10,
                }
            }
        }
        experiment = experiment_from_config(cfg)
        self.assertTrue(isinstance(
            experiment._experiment,
            ForcedVariantExperiment,
        ))
        self.assertIs(experiment.variant(), None)
        self.assertFalse(experiment.should_log_bucketing())

    def test_global_override_returns_forced_variant(self):
        cfg = {
            "id": "1",
            "name": "test",
            "owner": "test",
            "type": "legacy",
            "expires": int(time.time()) + THIRTY_DAYS_SEC,
            "global_override": "foo",
            "experiment": {
                "id": "1",
                "name": "test",
                "variants": {
                    "control_1": 10,
                    "control_2": 10,
                }
            }
        }
        experiment = experiment_from_config(cfg)
        self.assertTrue(isinstance(
            experiment._experiment,
            ForcedVariantExperiment),
        )

    def test_disable_returns_forced_variant(self):
        cfg = {
            "id": "1",
            "name": "test",
            "owner": "test",
            "type": "legacy",
            "expires": int(time.time()) + THIRTY_DAYS_SEC,
            "enabled": False,
            "experiment": {
                "id": "1",
                "name": "test",
                "variants": {
                    "control_1": 10,
                    "control_2": 10,
                }
            }
        }
        experiment = experiment_from_config(cfg)
        self.assertTrue(isinstance(
            experiment._experiment,
            ForcedVariantExperiment),
        )

    def test_forced_variant(self):
        experiment = ForcedVariantExperiment("foo")
        self.assertIs(experiment.variant(), "foo")
        self.assertFalse(experiment.should_log_bucketing())

    def test_forced_variant_null(self):
        experiment = ForcedVariantExperiment(None)
        self.assertIs(experiment.variant(), None)
        self.assertFalse(experiment.should_log_bucketing())
