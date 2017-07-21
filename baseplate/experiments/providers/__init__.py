from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import time

from .feature_flag import FeatureFlag
from .forced_variant import ForcedVariantExperiment
from .r2 import R2Experiment

logger = logging.getLogger(__name__)


def parse_experiment(config):
    """ Factory method that parses an experiment config dict and returns an
    appropriate Experiment class.

    The config dict is expected to have the following format:

        {
            "id": Integer experiment ID, should be unique for each experiment.
            "name": String experiment name, should be unique for each
                experiment.
            "owner": The group or individual that owns this experiment.
            "expires": Date when this experiment expires as UTC epoch seconds.
            "enabled": Optional value, defaults to True.  If set to False,
                the experiment will be disabled and calls to experiment.variant
                will always return None and will not log bucketing events to
                the event pipeline.
            "global_override": Optional value.  If this is set, calls to
                experiment.variant will always return the override value and
                will not log bucketing events to the event pipeline.
            "type": String specifying the type of experiment to run.  If this
                value is not reconized, the experiment will be considered
                disabled.
            "experiment": The experiment config dict for the specific type of
                experiment.  The format of this is determined by the specific
                experiment type.
        }

    :param dict config: Configuration dict for the experiment you wish to run.
    :rtype baseplate.experiments.providers.base.Experiment:
    :return: A subclass of :py:class:`Experiment` for the given experiment
        type.
    """
    experiment_type = config["type"].lower()
    experiment_id = config["id"]
    assert isinstance(experiment_id, int)
    name = config["name"]
    owner = config.get("owner")
    experiment_config = config["experiment"]
    expiration = config["expires"]

    if int(time.time()) > expiration:
        return ForcedVariantExperiment(None)

    enabled = config.get("enabled", True)
    if not enabled:
        return ForcedVariantExperiment(None)

    if "global_override" in config:
        # We want to check if "global_override" is in config rather than
        # checking config.get("global_override") because global_override = None
        # is a valid setting.
        override = config.get("global_override")
        return ForcedVariantExperiment(override)

    if experiment_type == "r2":
        return R2Experiment.from_dict(
            id=experiment_id,
            name=name,
            owner=owner,
            config=experiment_config,
        )
    elif experiment_type == "feature_flag":
        return FeatureFlag.from_dict(
            id=experiment_id,
            name=name,
            owner=owner,
            config=experiment_config,
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
        return ForcedVariantExperiment(None)


__all__ = ["parse_experiment"]
