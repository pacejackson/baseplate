from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import hashlib

from .base import Experiment
from ..._compat import long, iteritems, string_types


logger = logging.getLogger(__name__)


class R2Experiment(Experiment):
    """ A "legacy", r2-style experiment. Should log bucketing events to the
    event pipeline.

    Note that this style of experiment caps the size of your variants such
    that:

    effective_variant_size = max(variant_size, (1/num_variants) * 100)
    """

    def __init__(self, id, name, owner, variants, seed=None,
                 bucket_val="user_id", targeting=None, overrides=None,
                 newer_than=None):
        targeting = targeting or {}
        overrides = overrides or {}
        self.targeting = {}
        self.overrides = {}
        for param, value in iteritems(targeting):
            assert isinstance(param, string_types)
            assert isinstance(value, list)
            self.targeting[param.lower()] = [
                v.lower() if isinstance(v, string_types) else v for v in value
            ]
        for param, value in iteritems(overrides):
            assert isinstance(param, string_types)
            assert isinstance(value, dict)
            key = param.lower()
            self.overrides[key] = {k.lower(): v for k, v in iteritems(value)}
        self.id = id
        self.name = name
        self.owner = owner
        self.seed = seed if seed else name
        self.num_buckets = 1000
        self.variants = variants
        self.bucket_val = bucket_val
        self.newer_than = newer_than

    @classmethod
    def from_dict(cls, id, name, owner, config):
        """ Parse the config dict and return a new R2Experiment object.

        The config dict is expected to have the following format:

        {
            "variants": Dict mapping variant names to their sizes. Variant
                sizes are expressed as numeric percentages rather than a
                fraction of 1 (that is, 1.5 means 1.5%, not 150%).
            "targeting": (Optional) Dict that maps the names of targeting
                parameters to lists of valid values.  When determining the
                variant of an experiment, the targeting parameters you want to
                use are passed in as kwargs to the call to experiment.variant.
            "overrides": (Optional) Dict that maps override parameters to dicts
                mapping values to the variant name you want to override the
                variant to. When determining the variant of an experiment, the
                override parameters you want to use are passed in as kwargs to
                the call to experiment.variant.
            "bucket_val": (Optional) Name of the parameter you want to use for
                bucketing.  This value must be passed to the call to
                experiment.variant as a kwarg.  Defaults to "user_id".
            "seed": (Optional) Overrides the seed for this experiment.  If this
                is not set, `name` is used as the seed.
            "newer_than": (Optional) The earliest time that a bucketing
                resource can have been created by in UTC epoch seconds.  If
                set, you must pass the time, in UTC epoch seconds, when the
                resource that you are bucketing was created to the call to
                experiment.variant as the "created" parameter. For example, if
                you are bucketing based on user_id, created would be set to the
                time when a User account was created or when an LoID cookie was
                generated.
        }

        :param int id: The id of the experiment from the base config.
        :param str name: The name of the experiment from the base config.
        :param str owner: The owner of the experiment from the base config.
        :param dict config: The "experiment" config dict from the base config.
        :rtype: :py:class:`baseplate.experiments.providers.r2.R2Experiment`
        """
        return cls(
            id=id,
            name=name,
            owner=owner,
            variants=config["variants"],
            targeting=config.get("targeting"),
            overrides=config.get("overrides"),
            seed=config.get("seed"),
            bucket_val=config.get("bucket_val", "user_id"),
            newer_than=config.get("newer_than"),
        )

    def bucketing_event_id(self, **kwargs):
        if kwargs.get(self.bucket_val):
            return ":".join(
                [self.name, self.bucket_val, str(kwargs[self.bucket_val])]
            )
        else:
            return None

    def should_log_bucketing(self):
        return True

    def variant(self, **kwargs):
        lower_kwargs = {k.lower(): v for k, v in iteritems(kwargs)}
        if self.bucket_val not in lower_kwargs:
            raise ValueError(
                "Must specify %s in call to variant for experiment %s.",
                self.bucket_val,
                self.name,
            )

        variant = self._check_overrides(**lower_kwargs)
        if variant is not None and variant in self.variants:
            return variant

        if not self._is_enabled(**lower_kwargs):
            return None

        bucket = self._calculate_bucket(lower_kwargs[self.bucket_val])
        return self._choose_variant(bucket)

    def _check_overrides(self, **kwargs):
        """ Check if any of the kwargs override the variant. """
        for override_arg in self.overrides:
            if override_arg in kwargs:
                values = kwargs[override_arg]
                if not isinstance(values, (list, tuple)):
                    values = [values]
                for value in values:
                    override = self.overrides[override_arg].get(value.lower())
                    if override is not None:
                        return override
        return None

    def _is_enabled(self, **kwargs):
        """ Check if the targeting parameters in kwargs allow us to perform
        the experiment.
        """
        for targeting_param, allowed_values in iteritems(self.targeting):
            if targeting_param in kwargs:
                targeting_values = kwargs[targeting_param]
                if not isinstance(targeting_values, (list, tuple)):
                    targeting_values = [targeting_values]
                if not isinstance(allowed_values, list):
                    allowed_values = [allowed_values]
                for value in targeting_values:
                    if value in allowed_values:
                        return True

        user_created = kwargs.get("user_created")
        if self.newer_than and user_created and user_created > self.newer_than:
            return True

        return False

    def _calculate_bucket(self, bucket_val):
        """Sort something into one of self.num_buckets buckets.

        :param bucket_val -- a string used for shifting the deterministic bucketing
                       algorithm.  In most cases, this will be an Account's
                       _fullname.
        :return int -- a bucket, 0 <= bucket < self.num_buckets
        """
        # Mix the experiment seed with the bucket_val so the same users don't
        # get bucketed into the same bucket for each experiment.
        seed_bytes = ("%s%s" % (self.seed, bucket_val)).encode()
        hashed = hashlib.sha1(seed_bytes)
        bucket = long(hashed.hexdigest(), 16) % self.num_buckets
        return bucket

    def _choose_variant(self, bucket):
        """Deterministically choose a percentage-based variant.

        The algorithm satisfies two conditions:

        1. It's deterministic (that is, every call with the same bucket and
           variants will result in the same answer).
        2. An increase in any of the variant percentages will keep the same
           buckets in the same variants as at the smaller percentage (that is,
           all buckets previously put in variant A will still be in variant A,
           all buckets previously put in variant B will still be in variant B,
           etc. and the increased percentages will be made of up buckets
           previously not assigned to a bucket).

        These attributes make it suitable for use in A/B experiments that may
        see an increase in their variant percentages post-enabling.

        :param bucket -- an integer bucket representation
        :param variants -- a dictionary of
                           <string:variant name>:<float:percentage> pairs.  If
                           any percentage exceeds 1/n percent, where n is the
                           number of variants, the percentage will be capped to
                           1/n.  These variants will be added to
                           DEFAULT_CONTROL_GROUPS to create the effective
                           variant set.
        :return string -- the variant name, or None if bucket doesn't fall into
                          any of the variants
        """
        # Say we have an experiment with two new things we're trying out for 2%
        # of users (A and B), a control group with 5% (C), and a pool of
        # excluded users (x).  The buckets will be assigned like so:
        #
        #     A B C A B C x x C x x C x x C x x x x x x x x x...
        #
        # This scheme allows us to later increase the size of A and B to 7%
        # while keeping the experience consistent for users in any group other
        # than excluded users:
        #
        #     A B C A B C A B C A B C A B C A B x A B x x x x...
        #
        # Rather than building this entire structure out in memory, we can use
        # a little bit of math to figure out just the one bucket's value.
        num_variants = len(self.variants)
        variant_names = sorted(self.variants.keys())
        # If the variants took up the entire set of buckets, which bucket would
        # we be in?
        candidate_variant = variant_names[bucket % num_variants]
        # Log a warning if this variant is capped, to help us prevent user (us)
        # error.  It's not the most correct to only check the one, but it's
        # easy and quick, and anything with that high a percentage should be
        # selected quite often.
        variant_fraction = self.variants[candidate_variant] / 100.0
        variant_cap = 1.0 / num_variants
        if variant_fraction > variant_cap:
            logger.warning(
                'Variant %s exceeds allowable percentage (%.2f > %.2f)',
                candidate_variant,
                variant_fraction,
                variant_cap,
            )
        # Variant percentages are expressed as numeric percentages rather than
        # a fraction of 1 (that is, 1.5 means 1.5%, not 150%); thus, at 100
        # buckets, buckets and percents map 1:1 with each other.  Since we may
        # have more than 100 buckets (causing each bucket to represent less
        # than 1% each), we need to scale up how far "right" we move for each
        # variant percent.
        bucket_multiplier = self.num_buckets / 100
        # Now check to see if we're far enough left to be included in the
        # variant percentage.
        bucket_limit = (
            self.variants[candidate_variant] *
            num_variants *
            bucket_multiplier
        )
        if bucket < bucket_limit:
            return candidate_variant
        else:
            return None
