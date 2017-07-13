
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import collections
import time
import unittest

from baseplate._compat import long, range
from baseplate.features import FeatureFlags, User, TargetingParams
from baseplate.features.feature import (
    feature_flag_from_config,
    FeatureFlag,
    GloballyDisabledFeatureFlag,
    GloballyEnabledFeatureFlag,
)
from baseplate.file_watcher import FileWatcher, WatchedFileNotAvailableError

from ... import mock

logger = logging.getLogger(__name__)


class TestFeatureFlags(unittest.TestCase):

    def setUp(self):
        super(TestFeatureFlags, self).setUp()
        self.mock_filewatcher = mock.Mock(spec=FileWatcher)
        self.user = User(name="gary", id="t2_beef", created=int(time.time()))
        self.targeting = TargetingParams()

    def test_enabled_matches_expected(self):
        self.mock_filewatcher.get_data.return_value = {
            "test": {
                "id": "1",
                "name": "test",
                "type": "basic",
                "feature": {},
            },
        }
        features = FeatureFlags(self.mock_filewatcher)

        with mock.patch("baseplate.features.feature.FeatureFlag.enabled") as p:
            p.return_value = True
            self.assertTrue(features.enabled(
                "test",
                self.user,
                self.targeting,
            ))
            p.return_value = False
            self.assertFalse(features.enabled(
                "test",
                self.user,
                self.targeting,
            ))

    def test_false_if_cant_load_config(self):
        self.mock_filewatcher.get_data.side_effect = WatchedFileNotAvailableError("path", None)  # noqa
        features = FeatureFlags(self.mock_filewatcher)
        self.assertFalse(features.enabled("test", self.user, self.targeting))

    def test_false_if_cant_parse_config(self):
        self.mock_filewatcher.get_data.side_effect = TypeError()
        features = FeatureFlags(self.mock_filewatcher)
        self.assertFalse(features.enabled("test", self.user, self.targeting))

    def test_false_if_cant_find_feature(self):
        self.mock_filewatcher.get_data.return_value = {
            "other_test": {
                "id": "1",
                "name": "test",
                "type": "basic",
                "feature": {},
            },
        }
        features = FeatureFlags(self.mock_filewatcher)
        self.assertFalse(features.enabled("test", self.user, self.targeting))


class TestFeatureFlagFromConfig(unittest.TestCase):

    def test_basic_type(self):
        cfg = {
            "id": "1",
            "name": "test",
            "type": "basic",
            "feature": {},
        }
        feature_flag = feature_flag_from_config(cfg)
        self.assertTrue(isinstance(feature_flag, FeatureFlag))

    def test_unknown_type_returns_disabled_experiment(self):
        cfg = {
            "id": "1",
            "name": "test",
            "type": "unknown",
            "feature": {},
        }
        feature_flag = feature_flag_from_config(cfg)
        self.assertTrue(isinstance(feature_flag, GloballyDisabledFeatureFlag))
        self.assertFalse(feature_flag.enabled(None, None))

    def test_global_override_off(self):
        cfg = {
            "id": "1",
            "name": "test",
            "type": "basic",
            "global_override": "off",
            "feature": {},
        }
        feature_flag = feature_flag_from_config(cfg)
        self.assertTrue(isinstance(feature_flag, GloballyDisabledFeatureFlag))
        self.assertFalse(feature_flag.enabled(None, None))

    def test_global_override_on(self):
        cfg = {
            "id": "1",
            "name": "test",
            "type": "basic",
            "global_override": "on",
            "feature": {},
        }
        feature_flag = feature_flag_from_config(cfg)
        self.assertTrue(isinstance(feature_flag, GloballyEnabledFeatureFlag))
        self.assertTrue(feature_flag.enabled(None, None))


class TestFeatureFlag(unittest.TestCase):

    def setUp(self):
        super(TestFeatureFlag, self).setUp()
        self.user = User(name="gary", id="t2_beef", created=int(time.time()))
        self.targeting = TargetingParams()

    def _assert_fuzzy_percent_true(self, results, percent):
        stats = collections.Counter(results)
        total = sum(stats.values())
        # _roughly_ `percent` should have been `True`
        diff = abs((float(stats[True]) / total) - (percent / 100.0))
        self.assertTrue(diff < 0.1)

    def test_calculate_bucket_value(self):
        cfg = {
            "id": "1",
            "name": "test",
            "type": "basic",
            "feature": {},
        }
        feature_flag = feature_flag_from_config(cfg)
        feature_flag.num_buckets = 1000
        self.assertEqual(feature_flag._calculate_bucket("t2_1"), long(236))
        cfg = {
            "id": "1",
            "name": "test",
            "type": "basic",
            "feature": {
                "seed": "test-seed",
            }
        }
        seeded_feature_flag = feature_flag_from_config(cfg)
        self.assertNotEqual(seeded_feature_flag.seed, feature_flag.seed)
        self.assertIsNot(seeded_feature_flag.seed, None)
        seeded_feature_flag.num_buckets = 1000
        self.assertEqual(
            seeded_feature_flag._calculate_bucket("t2_1"),
            long(595),
        )

    def test_enabled(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "basic",
            "global_override": "on",
        }
        feature_flag = feature_flag_from_config(cfg)
        self.assertTrue(feature_flag.enabled(self.user, self.targeting))

    def test_disabled(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "basic",
            "global_override": "off",
        }
        feature_flag = feature_flag_from_config(cfg)
        self.assertFalse(feature_flag.enabled(self.user, self.targeting))

    def test_admin_enabled(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "basic",
            "feature": {
                "targeting": {
                    "user_flags": ["admin"],
                },
            },
        }
        feature_flag = feature_flag_from_config(cfg)
        self.user.flags.add("admin")
        self.assertTrue(feature_flag.enabled(self.user, self.targeting))

    def test_admin_disabled(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "basic",
            "feature": {
                "targeting": {
                    "user_flags": ["admin"],
                },
            },
        }
        feature_flag = feature_flag_from_config(cfg)
        self.assertNotIn("admin", self.user.flags)
        self.assertFalse(feature_flag.enabled(self.user, self.targeting))

    def test_employee_enabled(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "basic",
            "feature": {
                "targeting": {
                    "user_flags": ["employee"],
                },
            },
        }
        feature_flag = feature_flag_from_config(cfg)
        self.user.flags.add("employee")
        self.assertTrue(feature_flag.enabled(self.user, self.targeting))

    def test_employee_disabled(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "basic",
            "feature": {
                "targeting": {
                    "user_flags": ["employee"],
                },
            },
        }
        feature_flag = feature_flag_from_config(cfg)
        self.assertNotIn("employee", self.user.flags)
        self.assertFalse(feature_flag.enabled(self.user, self.targeting))

    def test_beta_enabled(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "basic",
            "feature": {
                "targeting": {
                    "user_flags": ["beta"],
                },
            },
        }
        feature_flag = feature_flag_from_config(cfg)
        self.user.flags.add("beta")
        self.assertTrue(feature_flag.enabled(self.user, self.targeting))

    def test_beta_disabled(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "basic",
            "feature": {
                "targeting": {
                    "user_flags": ["beta"],
                },
            },
        }
        feature_flag = feature_flag_from_config(cfg)
        self.assertNotIn("beta", self.user.flags)
        self.assertFalse(feature_flag.enabled(self.user, self.targeting))

    def test_gold_enabled(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "basic",
            "feature": {
                "targeting": {
                    "user_flags": ["gold"],
                },
            },
        }
        feature_flag = feature_flag_from_config(cfg)
        self.user.flags.add("gold")
        self.assertTrue(feature_flag.enabled(self.user, self.targeting))

    def test_gold_disabled(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "basic",
            "feature": {
                "targeting": {
                    "user_flags": ["gold"],
                },
            },
        }
        feature_flag = feature_flag_from_config(cfg)
        self.assertNotIn("gold", self.user.flags)
        self.assertFalse(feature_flag.enabled(self.user, self.targeting))

    def test_percent_loggedin(self):
        num_users = 2000
        users = []
        for i in range(num_users):
            users.append(User(
                name=str(i),
                id="t2_%s" % str(i),
                created=int(time.time()),
            ))

        def simulate_percent_loggedin(wanted_percent):
            cfg = {
                "id": "1",
                "name": "test_feature",
                "type": "basic",
                "feature": {
                    "percent_logged_in": wanted_percent,
                },
            }
            feature_flag = feature_flag_from_config(cfg)
            return (feature_flag.enabled(x, self.targeting) for x in users)

        self.assertFalse(any(simulate_percent_loggedin(0)))
        self.assertTrue(all(simulate_percent_loggedin(100)))
        self._assert_fuzzy_percent_true(simulate_percent_loggedin(25), 25)
        self._assert_fuzzy_percent_true(simulate_percent_loggedin(10), 10)
        self._assert_fuzzy_percent_true(simulate_percent_loggedin(50), 50)
        self._assert_fuzzy_percent_true(simulate_percent_loggedin(99), 99)

    def test_percent_loggedout(self):
        num_users = 2000
        users = []
        for i in range(num_users):
            users.append(User(
                name=None,
                id="t2_%s" % str(i),
                created=int(time.time()),
            ))

        def simulate_percent_loggedout(wanted_percent):
            cfg = {
                "id": "1",
                "name": "test_feature",
                "type": "basic",
                "feature": {
                    "percent_logged_out": wanted_percent,
                },
            }
            feature_flag = feature_flag_from_config(cfg)
            return (feature_flag.enabled(x, self.targeting) for x in users)

        self.assertFalse(any(simulate_percent_loggedout(0)))
        self.assertTrue(all(simulate_percent_loggedout(100)))
        self._assert_fuzzy_percent_true(simulate_percent_loggedout(25), 25)
        self._assert_fuzzy_percent_true(simulate_percent_loggedout(10), 10)
        self._assert_fuzzy_percent_true(simulate_percent_loggedout(50), 50)
        self._assert_fuzzy_percent_true(simulate_percent_loggedout(99), 99)


    def test_url_enabled(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "basic",
            "feature": {
                "targeting": {
                    "url": "test_state",
                },
            },
        }
        self.targeting.url_features.append("test_state")
        feature_flag = feature_flag_from_config(cfg)
        self.assertTrue(feature_flag.enabled(self.user, self.targeting))
        self.targeting.url_features.append("x")
        self.assertTrue(feature_flag.enabled(self.user, self.targeting))

    def test_url_disabled(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "basic",
            "feature": {
                "targeting": {
                    "url": "test_state",
                },
            },
        }
        self.assertEqual(self.targeting.url_features, [])
        feature_flag = feature_flag_from_config(cfg)
        self.assertFalse(feature_flag.enabled(self.user, self.targeting))
        self.targeting.url_features.append("x")
        self.assertFalse(feature_flag.enabled(self.user, self.targeting))

    def test_user_in(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "basic",
            "feature": {
                "targeting": {
                    "users": ["Gary"],
                },
            },
        }
        feature_flag = feature_flag_from_config(cfg)
        self.assertTrue(feature_flag.enabled(self.user, self.targeting))

        all_uppercase = User(
            name="ALL_UPPERCASE",
            id="t2_f00d",
            created=int(time.time())
        )
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "basic",
            "feature": {
                "targeting": {
                    "users": ["ALL_UPPERCASE"],
                },
            },
        }
        feature_flag = feature_flag_from_config(cfg)
        self.assertTrue(feature_flag.enabled(all_uppercase, self.targeting))

        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "basic",
            "feature": {
                "targeting": {
                    "users": ["dave", "gary"],
                },
            },
        }
        feature_flag = feature_flag_from_config(cfg)
        self.assertTrue(feature_flag.enabled(self.user, self.targeting))

    def test_user_not_in(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "basic",
            "feature": {
                "targeting": {
                    "users": [""],
                },
            },
        }
        feature_flag = feature_flag_from_config(cfg)
        self.assertFalse(feature_flag.enabled(self.user, self.targeting))

        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "basic",
            "feature": {
                "targeting": {
                    "users": ["dave", "joe"],
                },
            },
        }
        feature_flag = feature_flag_from_config(cfg)
        self.assertFalse(feature_flag.enabled(self.user, self.targeting))

    def test_subreddit_in(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "basic",
            "feature": {
                "targeting": {
                    "subreddits": ["WTF"],
                },
            },
        }
        self.targeting.subreddit = "WTF"
        feature_flag = feature_flag_from_config(cfg)
        self.assertTrue(feature_flag.enabled(self.user, self.targeting))

        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "basic",
            "feature": {
                "targeting": {
                    "subreddits": ["wtf"],
                },
            },
        }
        self.targeting.subreddit = "WTF"
        feature_flag = feature_flag_from_config(cfg)
        self.assertTrue(feature_flag.enabled(self.user, self.targeting))

        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "basic",
            "feature": {
                "targeting": {
                    "subreddits": ["WTF", "aww"],
                },
            },
        }
        self.targeting.subreddit = "WTF"
        feature_flag = feature_flag_from_config(cfg)
        self.assertTrue(feature_flag.enabled(self.user, self.targeting))

    def test_subreddit_not_in(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "basic",
            "feature": {
                "targeting": {
                    "subreddits": [],
                },
            },
        }
        self.targeting.subreddit = "WTF"
        feature_flag = feature_flag_from_config(cfg)
        self.assertFalse(feature_flag.enabled(self.user, self.targeting))

        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "basic",
            "feature": {
                "targeting": {
                    "subreddits": ["aww", "wtfoobar"],
                },
            },
        }
        self.targeting.subreddit = "WTF"
        feature_flag = feature_flag_from_config(cfg)
        self.assertFalse(feature_flag.enabled(self.user, self.targeting))

    def test_subdomain_in(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "basic",
            "feature": {
                "targeting": {
                    "subdomains": ["BETA"],
                },
            },
        }
        self.targeting.subdomain = "beta"
        feature_flag = feature_flag_from_config(cfg)
        self.assertTrue(feature_flag.enabled(self.user, self.targeting))

        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "basic",
            "feature": {
                "targeting": {
                    "subdomains": ["beta"],
                },
            },
        }
        self.targeting.subdomain = "BETA"
        feature_flag = feature_flag_from_config(cfg)
        self.assertTrue(feature_flag.enabled(self.user, self.targeting))

        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "basic",
            "feature": {
                "targeting": {
                    "subdomains": ["www", "beta"],
                },
            },
        }
        self.targeting.subdomain = "beta"
        feature_flag = feature_flag_from_config(cfg)
        self.assertTrue(feature_flag.enabled(self.user, self.targeting))

    def test_subdomain_not_in(self):
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "basic",
            "feature": {
                "targeting": {
                    "subdomains": [],
                },
            },
        }
        self.targeting.subdomain = "beta"
        feature_flag = feature_flag_from_config(cfg)
        self.assertFalse(feature_flag.enabled(self.user, self.targeting))
        self.targeting.subdomain = ""
        self.assertFalse(feature_flag.enabled(self.user, self.targeting))

        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "basic",
            "feature": {
                "targeting": {
                    "subdomains": ["www", "betanauts"],
                },
            },
        }
        self.targeting.subdomain = "beta"
        feature_flag = feature_flag_from_config(cfg)
        self.assertFalse(feature_flag.enabled(self.user, self.targeting))

    def test_multiple(self):
        # is_admin, globally off should still be False
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "basic",
            "global_override": "off",
            "feature": {
                "targeting": {
                    "user_flags": ["admin"],
                },
            },
        }
        feature_flag = feature_flag_from_config(cfg)
        self.user.flags.add("admin")
        self.assertFalse(feature_flag.enabled(self.user, self.targeting))

        # globally on but not admin should still be True
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "basic",
            "global_override": "on",
            "feature": {
                "targeting": {
                    "user_flags": ["admin"],
                },
            },
        }
        feature_flag = feature_flag_from_config(cfg)
        if "admin" in self.user.flags:
            self.user.flags.remove("admin")
        self.assertNotIn("admin", self.user.flags)
        self.assertTrue(feature_flag.enabled(self.user, self.targeting))
        self.user.flags.add("admin")
        self.assertTrue(feature_flag.enabled(self.user, self.targeting))

        # no URL but admin should still be True
        cfg = {
            "id": "1",
            "name": "test_feature",
            "type": "basic",
            "feature": {
                "targeting": {
                    "user_flags": ["admin"],
                    "url": "test_featurestate",
                },
            },
        }
        feature_flag = feature_flag_from_config(cfg)
        self.assertEqual(self.targeting.url_features, [])
        self.user.flags.add("admin")
        self.assertTrue(feature_flag.enabled(self.user, self.targeting))
