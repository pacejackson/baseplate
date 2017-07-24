from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

from datetime import datetime

from .feature_flag import FeatureFlag
from .forced_variant import ForcedVariantExperiment
from .r2 import R2Experiment

from ..event_logger import NullEventLogger

logger = logging.getLogger(__name__)


ISO_DATE_FMT = "%Y-%d-%m"
VARIANT_NOT_SET = object()


class Experiment(object):

    def __init__(self, id, name, owner, event_logger, provider,
                 bucket_event_override=None, extra_event_fields=None):
        self.id = id
        self.name = name
        self.owner = owner
        self._logger = event_logger
        self._provider = provider
        self._has_sent_bucketing_event = False
        self._extra_event_fields = extra_event_fields or {}
        self._bucket_event_override = bucket_event_override
        self._unique_id = ".".join([
            str(self.id),
            self.name,
            self._provider.get_unique_id(),
        ])
        self._variant = VARIANT_NOT_SET

    @property
    def variant(self):
        """Determine which variant, if any, of this experiment is active.

        All arguments needed for bucketing, targeting, and variant overrides
        should be passed in as kwargs.  The parameter names are determined by
        the specific implementation of the Experiment interface.

        :rtype: :py:class:`str`
        :returns: The name of the enabled variant as a string if any variant is
        enabled.  If no variant is enabled, return None.
        """
        if self._variant is VARIANT_NOT_SET:
            self._variant = self._provider.get_variant()
        self._log_bucketing_event(self._variant)
        return self._variant

    @property
    def unique_id(self):
        return self._unique_id

    def _log_bucketing_event(self, variant):
        do_log = True

        if variant is None:
            do_log = False

        if self._has_sent_bucketing_event:
            do_log = False

        if self._bucket_event_override is not None:
            do_log = bool(self._bucket_event_override)

        if do_log:
            fields = dict(
                variant=variant,
                experiment_id=self.id,
                experiment_name=self.name,
                owner=self.owner,
            )
            fields.update(self._extra_event_fields)
            self._logger.log("bucketing_events", "bucket", **fields)
            self._has_sent_bucketing_event = True


def parse_experiment(config, event_logger, bucket_event_override=None,
                     extra_event_fields=None, **kwargs):
    """Factory method that parses an experiment config dict and returns an
    appropriate Experiment class.

    The config dict is expected to have the following values:

        * **id**: Integer experiment ID, should be unique for each experiment.
        * **name**: String experiment name, should be unique for each
          experiment.
        * **owner**: The group or individual that owns this experiment.
        * **expires**: Date when this experiment expires in ISO format
          (YYYY-MM-DD).  The experiment will expire at 00:00 UTC on the day
          after the specified date.  Once an experiment is expired, it is
          considered disabled.
        * **type**: String specifying the type of experiment to run.  If this
          value is not recognized, the experiment will be considered disabled.
        * **experiment**: The experiment config dict for the specific type of
          experiment.  The format of this is determined by the specific
          experiment type.
        * **enabled**:  (Optional) If set to False, the experiment will be
          disabled and calls to experiment.variant will always return None and
          will not log bucketing events to the event pipeline. Defaults to
          True.
        * **global_override**: (Optional) If this is set, calls to
          experiment.variant will always return the override value and will not
          log bucketing events to the event pipeline.

    :param dict config: Configuration dict for the experiment you wish to run.
    :rtype: :py:class:`baseplate.experiments.providers.base.Experiment`
    :return: A subclass of :py:class:`Experiment` for the given experiment
        type.
    """
    experiment_type = config["type"].lower()
    experiment_id = config["id"]
    assert isinstance(experiment_id, int)
    name = config["name"]
    owner = config.get("owner")
    experiment_config = config["experiment"]
    expiration = datetime.strptime(config["expires"], ISO_DATE_FMT).date()

    if datetime.utcnow().date() > expiration:
        return Experiment(
            id=experiment_id,
            name=name,
            owner=owner,
            event_logger=NullEventLogger(),
            provider=ForcedVariantExperiment(None),
        )

    enabled = config.get("enabled", True)
    if not enabled:
        return Experiment(
            id=experiment_id,
            name=name,
            owner=owner,
            event_logger=NullEventLogger(),
            bucket_event_override=bucket_event_override,
            extra_event_fields=extra_event_fields,
            provider=ForcedVariantExperiment(None),
        )

    if "global_override" in config:
        # We want to check if "global_override" is in config rather than
        # checking config.get("global_override") because global_override = None
        # is a valid setting.
        override = config.get("global_override")
        return Experiment(
            id=experiment_id,
            name=name,
            owner=owner,
            event_logger=NullEventLogger(),
            bucket_event_override=bucket_event_override,
            extra_event_fields=extra_event_fields,
            provider=ForcedVariantExperiment(override),
        )

    if experiment_type == "r2":
        return Experiment(
            id=experiment_id,
            name=name,
            owner=owner,
            event_logger=event_logger,
            bucket_event_override=bucket_event_override,
            extra_event_fields=extra_event_fields,
            provider=R2Experiment.from_dict(
                name=name,
                config=experiment_config,
                **kwargs
            ),
        )
    elif experiment_type == "feature_flag":
        return Experiment(
            id=experiment_id,
            name=name,
            owner=owner,
            event_logger=NullEventLogger(),
            bucket_event_override=bucket_event_override,
            extra_event_fields=extra_event_fields,
            provider=FeatureFlag.from_dict(
                name=name,
                config=experiment_config,
                **kwargs
            ),
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
        return Experiment(
            id=experiment_id,
            name=name,
            owner=owner,
            event_logger=NullEventLogger(),
            bucket_event_override=bucket_event_override,
            extra_event_fields=extra_event_fields,
            provider=ForcedVariantExperiment(None),
        )


__all__ = ["parse_experiment"]
