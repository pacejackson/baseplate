
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
    """ Parse the feature flag configuration dict and return an instance of a
    class that implements the baseplate.features.feature.FeatureFlagInterface
    interface.  The specific class depends on the "type" of feature flag and
    whether any global overrides are set.

    The config dict is expected to have the following format:

    {
        "id": The id of the feature as a string
        "name": The name of the feature as a string
        "type": The type of feature.  Only "basic" is currently supported
        "feature": The config dict for the specific feature, this will vary
            depending on the type of feature
        "global_override": Optional value that can be set to "on" or "off".
            If set to "on", we will return a feature flag that is always
            enabled and if set to "off", we will return a feature flag that
            is always disabled.  Any other values are ignored.
    }

    :param dict config: A feature flag configuration dict.
    :rtype baseplate.features.feature.FeatureFlagInterface:
    :returns: A feature flag object that implements the FetureFlag Interface.
    """
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
    """ Base interface for feature flag objects. """

    def enabled(self, user, targeting):
        """ Return if the feature should be enabled for the given user and
        targeting values.

        :param baseplate.features.User user:
        :param baseplate.featurs.TargetingParams targeting:
        :rtype bool:
        :return: True if the feature should be enabled, False if not.
        """
        raise NotImplementedError


class GloballyEnabledFeatureFlag(FeatureFlagInterface):
    """ A feature flag that is always enabled. """

    def enabled(self, user, targeting):
        return True


class GloballyDisabledFeatureFlag(FeatureFlagInterface):
    """ A feature flag that is always disabled. """

    def enabled(self, user, targeting):
        return False


class FeatureTargeting(object):
    """ Targeting configuration for a "basic" FeatureFlag. """

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
    """ A "basic" feature flag.  Provides targeting against discrete values and
    a percentage of users based on ID.
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
        """ Parse the config dict and return a new FeatureFlag object.

        The config dict is expected to have the following format:

        {
            "percent_logged_in": Optional value.  The percentage of logged
                in users that you want to enable the feature for as an integer
                0 - 100.  If this is not set, it defaults to 0.
            "percent_logged_out": Optional value.  The percentage of logged
                out users that you want to enable the feature for as an integer
                0 - 100.  If this is not set, it defaults to 0.
        }

        :param str id: The ID of the feature from the base config.
        :param str name: The name of the feature from the base config.
        :param str owner: The owner of the feature from the base config.
        :param dict config: The "feature" config dict from the base config.
        :rtype: baseplate.features.feature.FeatureFlag
        """
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
        """Sort something into one of self.num_buckets buckets.

        :param bucket_val -- a string used for shifting the deterministic bucketing
                       algorithm.  In most cases, this will be an Account's
                       _fullname.
        :return int -- a bucket, 0 <= bucket < self.num_buckets
        """
        # Mix the feature name in with the seed so the same users don't get
        # selected for ramp-ups for every feature.
        seed_bytes = ("%s%s" % (self.seed, bucket_val)).encode()
        hashed = hashlib.sha1(seed_bytes)
        bucket = long(hashed.hexdigest(), 16) % self.num_buckets
        return bucket

    def enabled(self, user, targeting):
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
