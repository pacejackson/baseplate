
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

from baseplate.experiments.providers import experiment_from_config
from baseplate.experiments.providers.forced_variant import ForcedVariantExperiment


class TestForcedVariantExperiment(unittest.TestCase):

    def test_unknown_type_returns_null_experiment(self):
        cfg = {
            "id": "1",
            "name": "test",
            "owner": "test",
            "type": "unknown",
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
        self.assertTrue(isinstance(experiment, ForcedVariantExperiment))
        self.assertIs(experiment.variant(), None)
        self.assertFalse(experiment.should_log_bucketing())

    def test_global_override_returns_forced_variant(self):
        cfg = {
            "id": "1",
            "name": "test",
            "owner": "test",
            "type": "legacy",
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
        self.assertTrue(isinstance(experiment, ForcedVariantExperiment))

    def test_forced_variant(self):
        experiment = ForcedVariantExperiment("id", "name", "owner", "foo")
        self.assertIs(experiment.variant(), "foo")
        self.assertFalse(experiment.should_log_bucketing())

    def test_forced_variant_null(self):
        experiment = ForcedVariantExperiment("id", "name", "owner", None)
        self.assertIs(experiment.variant(), None)
        self.assertFalse(experiment.should_log_bucketing())