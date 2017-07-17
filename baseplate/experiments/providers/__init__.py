
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

from .forced_variant import ForcedVariantExperiment
from .legacy import LegacyExperiment
from ...features.feature import feature_flag_from_config

logger = logging.getLogger(__name__)


class ExperimentManager(object):

    def __init__(self, id, name, owner, experiment, enabled=True,
                 feature_flag=None):
        self.id = id,
        self.name = name
        self.owner = owner
        self._experiment = experiment
        self._enabled = enabled
        self._feature_flag = feature_flag

    def enabled(self, **feature_args):
        if not self._enabled:
            return False

        if self._feature_flag is None:
            return True

        if self._feature_flag.enabled(**feature_args):
            return True

        return False

    def variant(self, *a, **kw):
        return self._experiment.variant(*a, **kw)

    def should_log_bucketing(self):
        return self._experiment.should_log_bucketing()

    def event_params(self):
        event_params = {
            "experiment_id": self.id,
            "experiment_name": self.name,
            "experiment_owner": self.owner,
        }
        return event_params


def experiment_from_config(config):
    experiment_type = config["type"].lower()
    experiment_id = config["id"]
    name = config["name"]
    owner = config.get("owner")
    experiment_config = config["experiment"]
    override = config.get("global_override")
    enabled = config.get("enabled", True)
    if override:
        logger.warning(
            "Found an experiment with a global override <%s:%s> that is owned "
            "by <%s>. Please clean up.",
            experiment_id,
            name,
            owner,
        )
        return ExperimentManager(
            id=experiment_id,
            name=name,
            owner=owner,
            experiment=ForcedVariantExperiment(override)
        )
    if not enabled:
        logger.warning(
            "Found a disabled experiment <%s:%s> that is owned by <%s>. "
            "Please clean up.",
            experiment_id,
            name,
            owner,
        )
        return ExperimentManager(
            id=experiment_id,
            name=name,
            owner=owner,
            experiment=ForcedVariantExperiment(None),
        )

    if "feature" in config:
        feature_flag = feature_flag_from_config(config["feature"])
    else:
        feature_flag = None
    if experiment_type == "legacy":
        return ExperimentManager(
            id=experiment_id,
            name=name,
            owner=owner,
            enabled=enabled,
            feature_flag=feature_flag,
            experiment=LegacyExperiment.from_config(name, experiment_config),
        )
    else:
        logger.warning(
            "Found an experiment <%s:%s> with an unknown experiment type <%s> "
            "that is owned by <%s>. Please clean up.",
            experiment_id,
            name,
            experiment_type,
            owner,
        )
        return ExperimentManager(
            id=experiment_id,
            name=name,
            owner=owner,
            experiment=ForcedVariantExperiment(None),
        )


__all__ = ["experiment_from_config"]
