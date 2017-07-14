
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import hashlib

from .base import ExperimentInterface
from ..._compat import long, iteritems


logger = logging.getLogger(__name__)


class LegacyExperiment(ExperimentInterface):

    EXPERIMENT_TYPES = {"page", "user"}

    def __init__(self, id, name, owner, type, variants, url_variants=None,
                 content_flags=None, seed=None, enabled=True, feature=None):
        super(LegacyExperiment, self).__init__(id, name, owner)
        url_variants = url_variants or {}
        content_flags = content_flags or {}
        assert type in self.EXPERIMENT_TYPES
        assert set(url_variants.values()) - set(variants.keys()) == set()
        self.seed = seed if seed else name
        self.num_buckets = 1000
        self.type = type
        self.owner = owner
        self.content_flags = content_flags
        self.variants = variants
        self.url_variants = url_variants
        self.enabled = enabled
        self.feature = feature

    @classmethod
    def from_config(cls, id, name, owner, config):
        from ...features.feature import feature_flag_from_config
        if config.get('page'):
            experiment_type = "page"
        else:
            experiment_type = "user"
        variants = config.get("variants", {})
        url_variants = {}
        for url_flag, variant in iteritems(config.get("url", {})):
            if variant not in variants:
                logger.warning(
                    "Undefined url variant <%s:%s> in experiment <%s:%s>",
                    url_flag,
                    variant,
                    config["id"],
                    config["name"],
                )
            else:
                url_variants[url_flag] = variant
        if "feature" in config:
            feature_flag = feature_flag_from_config(config["feature"])
        else:
            feature_flag = None
        return cls(
            id=id,
            name=name,
            owner=owner,
            type=experiment_type,
            seed=config.get("seed"),
            variants=variants,
            url_variants=url_variants,
            content_flags=config.get("content_flags", {}),
            enabled=config.get("enabled", True),
            feature=feature_flag,
        )

    def should_log_bucketing(self):
        return True

    def variant(self, user, content, url_flags):
        """ Determine which variant of this experiment, if any, is active. """

        if not self.enabled:
            return None

        if url_flags and self.url_variants:
            for flag in url_flags:
                if flag in self.url_variants:
                    return self.url_variants[flag]

        if self.type == "user":
            return self._get_user_experiment_variant(user)
        elif self.type == "page":
            return self._get_page_experiment_variant(content)
        else:
            logger.warning(
                "Experiment <%s:%s> with unkown type %s",
                self.id,
                self.name,
                self.type,
            )
            return None

    def _calculate_bucket(self, bucket_val):
        """Sort something into one of self.num_buckets buckets.

        :param seed -- a string used for shifting the deterministic bucketing
                       algorithm.  In most cases, this will be an Account's
                       _fullname.
        :param feature_seed -- a unique id used for shifting the
                        deterministic bucketing algorithm when we want to
                        bucket a fresh group of users without changing the
                        feature flag name. This should be a unique id that
                        has not previously been in this experiment.
        :return int -- a bucket, 0 <= bucket < self.num_buckets
        """
        # Mix the feature name in with the seed so the same users don't get
        # selected for ramp-ups for every feature.
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

    def _get_page_experiment_variant(self, content):
        bucket = self._get_thing_bucket(content)
        if bucket is None:
            return None
        return self._choose_variant(bucket)

    def _get_user_experiment_variant(self, user):
        if user.id is None:
            return None

        bucket = self._calculate_bucket(user.id)
        return self._choose_variant(bucket)

    def _get_thing_bucket(self, content):
        if content.id is None:
            return None

        # If we've restricted the experiment to certain page types, make sure
        # the request is for one of those
        if (self.content_flags.get('subreddit_only', False) and
                content.type != 'subreddit'):
            return None

        if (self.content_flags.get('link_only', False) and
                (content.type != 'link' and content.type != 'comment')):
            # We treat comment permalink pages like general comments pages
            return None

        return self._calculate_bucket(content.id)
