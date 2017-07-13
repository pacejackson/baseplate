
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import hashlib

from .._compat import long


logger = logging.getLogger(__name__)


# Special values for globally enabled properties - no need to interrogate
# the world for these values.
GLOBALLY_ON = "on"
GLOBALLY_OFF = "off"


def feature_flag_from_config(config):
    name = config["name"]
    feature_type = config["type"]
    owner = config.get("owner")
    feature_id = config.get("id")
    override = config.get("global_override")
    if override == GLOBALLY_ON:
        logger.warning(
            "Found globally enabled feature flag <%s> that is owned by "
            "<%s>. Please clean up.",
            name,
            owner,
        )
        return GloballyEnabledFeatureFlag()
    if override == GLOBALLY_OFF:
        logger.warning(
            "Found globally disabled feature flag <%s> that is owned by "
            "<%s>. Please clean up.",
            name,
            owner,
        )
        return GloballyDisabledFeatureFlag()

    feature_config = config["feature"]

    if feature_type == "basic":
        return FeatureFlag.from_config(feature_id, name, owner, feature_config)
    else:
        logger.warning(
            "Found an feature <%s> with an unknown feature type <%s> "
            "that is owned by <%s>. Please clean up.",
            name,
            feature_type,
            owner,
        )
        return GloballyDisabledFeatureFlag()


class FeatureFlagInterface(object):

    def enabled(self, user, targeting):
        raise NotImplementedError


class GloballyEnabledFeatureFlag(FeatureFlagInterface):

    def enabled(self, user, targeting):
        return True


class GloballyDisabledFeatureFlag(FeatureFlagInterface):

    def enabled(self, user, targeting):
        return False


class FeatureTargeting(object):

    EXPECTED_USER_FLAGS = {"admin", "sponsor", "employee", "beta", "gold"}

    def __init__(self, user_flags, newer_than, users, subreddits, subdomains,
                 oauth_clients, url_flag):
        assert not user_flags - self.EXPECTED_USER_FLAGS
        self.user_flags = user_flags
        self.newer_than = newer_than
        self.users = users
        self.subreddits = subreddits
        self.subdomains = subdomains
        self.oauth_clients = oauth_clients
        self.url_flag = url_flag

    @classmethod
    def from_config(cls, config):
        user_flags = config.get("user_flags", [])
        user_flags = set([flag.lower() for flag in user_flags])
        users = config.get("users", [])
        users = set([user.lower() for user in users])
        subreddits = config.get("subreddits", [])
        subreddits = set([subreddit.lower() for subreddit in subreddits])
        subdomains = config.get("subdomains", [])
        subdomains = set([subdomain.lower() for subdomain in subdomains])
        oauth_clients = config.get("oauth_clients", [])
        oauth_clients = set([client.lower() for client in oauth_clients])
        return cls(
            user_flags=user_flags,
            newer_than=config.get("newer_than"),
            users=users,
            subreddits=subreddits,
            subdomains=subdomains,
            oauth_clients=oauth_clients,
            url_flag=config.get("url")
        )


class FeatureFlag(FeatureFlagInterface):
    """A FeatureState is the state of a feature and its condition in the world.

    It determines if this feature is enabled given the world provided.
    """

    def __init__(self, id, name, owner, seed, percent_logged_in,
                 percent_logged_out, targeting):
        self.id = id
        self.name = name
        self.owner = owner
        self.num_buckets = 1000
        self.seed = seed if seed else self.name
        self.percent_logged_in = percent_logged_in
        self.percent_logged_out = percent_logged_out
        self.targeting = targeting

    @classmethod
    def from_config(cls, id, name, owner, config):
        return cls(
            id=id,
            name=name,
            owner=owner,
            seed=config.get('seed'),
            percent_logged_in=config.get('percent_logged_in', 0),
            percent_logged_out=config.get('percent_logged_out', 0),
            targeting=FeatureTargeting.from_config(config.get('targeting', {}))
        )

    def _calculate_bucket(self, bucket_val):
        """Sort something into one of self.NUM_BUCKETS buckets.

        :param bucket_val -- a string used for shifting the deterministic bucketing
                       algorithm.  In most cases, this will be an Account's
                       _fullname.
        :return int -- a bucket, 0 <= bucket < self.NUM_BUCKETS
        """
        # Mix the feature name in with the seed so the same users don't get
        # selected for ramp-ups for every feature.
        seed_bytes = ("%s%s" % (self.seed, bucket_val)).encode()
        hashed = hashlib.sha1(seed_bytes)
        bucket = long(hashed.hexdigest(), 16) % self.num_buckets
        return bucket

    def enabled(self, user, targeting):
        """ Determine if a feature is enabled. """

        # first, test if the feature is enabled off of the targeting
        # parameters
        if self._is_targeting_enabled(user, targeting):
            return True

        # next, test if the feature is enabled fractionally
        if self._is_percent_enabled(user):
            return True

        # default to off.
        return False

    def _is_targeting_enabled(self, user, targeting):

        for feature in targeting.url_features:
            if feature == self.targeting.url_flag:
                return True

        for user_flag in self.targeting.user_flags:
            if user_flag in user.flags:
                return True

        if self.targeting.newer_than and user.created < self.targeting.newer_than:
            return True

        if (
            self.targeting.users and
            user.logged_in and
            user.name.lower() in self.targeting.users
        ):
            return True

        if (
            self.targeting.subreddits and
            targeting.subreddit and
            targeting.subreddit.lower() in self.targeting.subreddits
        ):
            return True

        if (
            self.targeting.subdomains and
            targeting.subdomain and
            targeting.subdomain.lower() in self.targeting.subdomains
        ):
            return True

        if (
            self.targeting.oauth_clients and
            targeting.oauth_client and
            targeting.oauth_client.lower() in self.targeting.oauth_clients
        ):
            return True

    def _is_percent_enabled(self, user):
        if user.id is None:
            return False

        if user.logged_in:
            percentage = self.percent_logged_in
        else:
            percentage = self.percent_logged_out

        if percentage is None:
            return False
        if percentage <= 0:
            return False
        if percentage >= 100:
            return True
        bucket = self._calculate_bucket(user.id)
        scaled_percent = bucket / (self.num_buckets / 100)
        if scaled_percent < percentage:
            return True


__all__ = ["feature_flag_from_config"]
