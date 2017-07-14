
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

from .forced_variant import ForcedVariantExperiment
from .legacy import LegacyExperiment

logger = logging.getLogger(__name__)


def experiment_from_config(config):
    experiment_type = config["type"].lower()
    experiment_id = config["id"]
    name = config["name"]
    owner = config.get("owner")
    experiment_config = config["experiment"]
    override = config.get("global_override")
    if override:
        logger.warning(
            "Found an experiment with a global override <%s:%s> that is owned "
            "by <%s>. Please clean up.",
            experiment_id,
            name,
            owner,
        )
        return ForcedVariantExperiment(experiment_id, name, owner, override)
    if experiment_type == "legacy":
        return LegacyExperiment.from_config(
            id=id,
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
        return ForcedVariantExperiment(experiment_id, name, owner, None)


__all__ = ["experiment_from_config"]
