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
    experiment_type = config["type"].lower()
    experiment_id = config["id"]
    name = config["name"]
    owner = config.get("owner")
    experiment_config = config["experiment"]
    expiration = config["expires"]
    if int(time.time()) > expiration:
        logger.warning(
            "Found an expired experiment <%s:%s> that is owned by <%s>. "
            "Please clean up.",
            experiment_id,
            name,
            owner,
        )
        return ForcedVariantExperiment(None)
    enabled = config.get("enabled", True)
    if not enabled:
        logger.warning(
            "Found a disabled experiment <%s:%s> that is owned by <%s>. "
            "Please clean up.",
            experiment_id,
            name,
            owner,
        )
        return ForcedVariantExperiment(None)
    if "global_override" in config:
        override = config.get("global_override")
        logger.warning(
            "Found an experiment with a global override <%s:%s> that is owned "
            "by <%s>. Please clean up.",
            experiment_id,
            name,
            owner,
        )
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
